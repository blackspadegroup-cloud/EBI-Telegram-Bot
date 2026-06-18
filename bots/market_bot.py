"""
bots/market_bot.py – Bot 1: AI Market Analysis Bot

Responsibilities:
  - Posts market updates at 07:00, 14:00, 19:00 (Asia/Singapore)
  - Monitors for breaking news every 15 minutes
  - Monitors economic calendar and alerts 30 min before high-impact events
  - Admin commands: /testnews, /pause, /resume, /stats, /help, /broadcast

Run schedule (APScheduler, Asia/Singapore timezone):
  Cron:    07:00, 14:00, 19:00 → post_scheduled_update()
  Interval: every 15 min       → check_breaking_news()
  Interval: every 30 min       → check_economic_calendar()
"""

import asyncio
from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import config
from database import (
    get_message_stats,
    get_member_count,
    is_news_already_sent,
    log_message,
    mark_news_sent,
)
from services.ai import (
    generate_breaking_news_alert,
    generate_economic_event_alert,
    generate_market_update,
)
from services.calendar import get_events_to_alert
from services.formatter import (
    format_price_header,
    format_scheduled_post,
    format_stats,
    truncate,
)
from services.news import (
    check_for_breaking_news,
    fetch_btc_news,
    fetch_gold_news,
    format_headlines_for_ai,
)
from services.prices import get_btc_data, get_gold_data
from utils.logger import get_logger

log = get_logger("market_bot")


# ── Admin guard decorator ─────────────────────────────────────────────────────

def admin_only(func):
    """Decorator: only allow commands from configured admin IDs."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ You are not authorized to use this command.")
            log.warning(f"Unauthorized admin command attempt by user {user_id}")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Core posting logic ────────────────────────────────────────────────────────

async def post_scheduled_update(bot: Bot) -> None:
    """
    Fetch prices + news, generate AI summary, post to the group.
    Called by the scheduler at 07:00, 14:00, 19:00.
    """
    if config.BOT_PAUSED:
        log.info("Bot is paused — skipping scheduled update")
        return

    log.info("Starting scheduled market update...")

    try:
        # Fetch data concurrently
        gold_data, btc_data, gold_news, btc_news = await asyncio.gather(
            get_gold_data(),
            get_btc_data(),
            fetch_gold_news(hours_back=6),
            fetch_btc_news(hours_back=6),
        )

        # Inject news headlines into data dicts for AI
        gold_data["news_headlines"] = format_headlines_for_ai(gold_news)
        btc_data["news_headlines"] = format_headlines_for_ai(btc_news)

        # Generate AI content
        ai_content = await generate_market_update(gold_data, btc_data)
        if not ai_content:
            log.error("AI failed to generate market update")
            return

        # Compose final message
        header = format_price_header(gold_data, btc_data)
        message = format_scheduled_post(header, ai_content)
        message = truncate(message)

        # Send to group
        await bot.send_message(
            chat_id=config.MARKET_GROUP_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )

        log_message("market_bot", "scheduled", message, config.MARKET_GROUP_ID)
        log.info("Scheduled update posted successfully")

    except Exception as e:
        log.error(f"post_scheduled_update failed: {e}", exc_info=True)


async def check_breaking_news(bot: Bot) -> None:
    """
    Scan for high-impact breaking news and post if found.
    Called every 15 minutes by the scheduler.
    """
    if config.BOT_PAUSED:
        return

    try:
        breaking = await check_for_breaking_news(hours_back=1)

        for item in breaking:
            title = item["title"]

            # Skip if already sent
            if is_news_already_sent(title):
                continue

            asset = item.get("asset", "both")
            alert = await generate_breaking_news_alert(title, asset)
            if not alert:
                continue

            await bot.send_message(
                chat_id=config.MARKET_GROUP_ID,
                text=truncate(alert),
                parse_mode=ParseMode.MARKDOWN,
            )

            mark_news_sent(title)
            log_message("market_bot", "breaking", alert, config.MARKET_GROUP_ID)
            log.info(f"Breaking news alert sent: {title[:60]}")

            # Small delay between multiple alerts
            await asyncio.sleep(2)

    except Exception as e:
        log.error(f"check_breaking_news failed: {e}", exc_info=True)


async def check_economic_calendar(bot: Bot) -> None:
    """
    Check for upcoming high-impact economic events and send pre-event alerts.
    Called every 30 minutes by the scheduler.
    """
    if config.BOT_PAUSED:
        return

    try:
        events = await get_events_to_alert(alert_window_minutes=30)

        for event in events:
            alert = await generate_economic_event_alert(event)
            if not alert:
                continue

            await bot.send_message(
                chat_id=config.MARKET_GROUP_ID,
                text=truncate(alert),
                parse_mode=ParseMode.MARKDOWN,
            )

            log_message("market_bot", "calendar_alert", alert, config.MARKET_GROUP_ID)
            log.info(f"Calendar alert sent: {event['name']}")
            await asyncio.sleep(2)

    except Exception as e:
        log.error(f"check_economic_calendar failed: {e}", exc_info=True)


# ── Admin command handlers ────────────────────────────────────────────────────

@admin_only
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available admin commands."""
    text = (
        "🤖 *Market Bot – Admin Commands*\n\n"
        "/testnews – Trigger a market update right now\n"
        "/pause – Pause all scheduled posts\n"
        "/resume – Resume all scheduled posts\n"
        "/stats – View bot statistics\n"
        "/broadcast `<message>` – Send a custom message to the group\n"
        "/help – Show this message"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_testnews(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger a market update."""
    await update.message.reply_text("⚙️ Generating market update...")
    bot = ctx.bot
    await post_scheduled_update(bot)
    await update.message.reply_text("✅ Update sent.")


@admin_only
async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause all automatic posts."""
    config.BOT_PAUSED = True
    await update.message.reply_text("⏸️ Market bot paused. Use /resume to restart.")
    log.info(f"Bot paused by admin {update.effective_user.id}")


@admin_only
async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume all automatic posts."""
    config.BOT_PAUSED = False
    await update.message.reply_text("▶️ Market bot resumed.")
    log.info(f"Bot resumed by admin {update.effective_user.id}")


@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot stats."""
    member_count = get_member_count()
    market_stats = get_message_stats("market_bot", days=7)
    community_stats = get_message_stats("community_bot", days=7)
    text = format_stats(member_count, market_stats, community_stats)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast a custom message to the market group."""
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return
    message = " ".join(ctx.args)
    await ctx.bot.send_message(
        chat_id=config.MARKET_GROUP_ID,
        text=f"📢 *Announcement*\n\n{message}",
        parse_mode=ParseMode.MARKDOWN,
    )
    log_message("market_bot", "broadcast", message, config.MARKET_GROUP_ID)
    await update.message.reply_text("✅ Broadcast sent.")


# ── Bot builder ───────────────────────────────────────────────────────────────

def build_market_bot() -> tuple[Application, AsyncIOScheduler]:
    """
    Build and configure the Market Bot application + APScheduler.
    Returns (application, scheduler) — both must be started by main.py.
    """
    app = Application.builder().token(config.MARKET_BOT_TOKEN).build()

    # Register admin command handlers
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("testnews", cmd_testnews))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # Set up scheduler
    tz = pytz.timezone(config.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    bot = app.bot

    # Scheduled market updates: 07:00, 14:00, 19:00 local time
    for hour in config.SCHEDULE_HOURS:
        scheduler.add_job(
            post_scheduled_update,
            trigger="cron",
            hour=hour,
            minute=0,
            args=[bot],
            id=f"scheduled_update_{hour:02d}h",
            replace_existing=True,
        )

    # Breaking news check every 15 minutes
    scheduler.add_job(
        check_breaking_news,
        trigger="interval",
        minutes=config.NEWS_CHECK_INTERVAL,
        args=[bot],
        id="breaking_news_check",
        replace_existing=True,
    )

    # Economic calendar check every 30 minutes
    scheduler.add_job(
        check_economic_calendar,
        trigger="interval",
        minutes=30,
        args=[bot],
        id="calendar_check",
        replace_existing=True,
    )

    log.info(
        f"Market bot configured. Schedule: {config.SCHEDULE_HOURS} {config.TIMEZONE}, "
        f"news check every {config.NEWS_CHECK_INTERVAL} min"
    )
    return app, scheduler
