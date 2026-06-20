"""
bots/market_bot.py – Bot 1: AI Market Analysis Bot

Schedules (Asia/Singapore timezone):
  Mon–Fri  07:00, 14:00, 19:00 → 3 AI market update versions sent to approval group
  Sat–Sun  20:00               → 3 AI mindset versions sent to approval group

Approval workflow:
  1. Bot generates 3 versions and posts them to APPROVAL_GROUP_ID
  2. Steve (or boss) taps a "✅ Send Version X" button
  3. Bot sends the chosen version to MARKET_GROUP_ID (the community)
  4. If nobody picks within 30 minutes, Version 1 auto-posts

Breaking news + economic calendar alerts go directly to the community group.

Admin commands: /testnews, /testmindset, /pause, /resume, /stats, /broadcast, /help
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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
    generate_mindset_content,
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

# ── Approval state ────────────────────────────────────────────────────────────
# uid → { versions: [...], task: asyncio.Task, sent: bool }
_pending_approvals: dict = {}


# ── Admin guard ───────────────────────────────────────────────────────────────

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


# ── Approval workflow ─────────────────────────────────────────────────────────

async def post_for_approval(bot: Bot, content_type: str = "market") -> None:
    """
    Generate 3 AI versions and send them to the approval group.
    Each version gets its own inline button.
    Auto-sends Version 1 after 30 minutes if no selection is made.

    content_type: "market" (Mon–Fri updates) or "mindset" (Sat–Sun posts)
    """
    if config.BOT_PAUSED:
        log.info("Bot is paused — skipping approval request")
        return

    label = "📊 Market Update" if content_type == "market" else "💭 Weekend Mindset"
    log.info(f"Generating 3 versions for approval ({content_type})…")

    try:
        versions = []

        if content_type == "market":
            # Fetch price + news data once, then generate 3 AI versions concurrently
            gold_data, btc_data, gold_news, btc_news = await asyncio.gather(
                get_gold_data(),
                get_btc_data(),
                fetch_gold_news(hours_back=6),
                fetch_btc_news(hours_back=6),
            )
            gold_data["news_headlines"] = format_headlines_for_ai(gold_news)
            btc_data["news_headlines"] = format_headlines_for_ai(btc_news)
            header = format_price_header(gold_data, btc_data)

            ai_results = await asyncio.gather(
                generate_market_update(gold_data, btc_data, perspective="technical"),
                generate_market_update(gold_data, btc_data, perspective="fundamental"),
                generate_market_update(gold_data, btc_data, perspective="sentiment"),
            )
            for result in ai_results:
                if result:
                    msg = format_scheduled_post(header, result)
                    versions.append(truncate(msg))

        else:  # mindset
            ai_results = await asyncio.gather(
                generate_mindset_content(topic="discipline"),
                generate_mindset_content(topic="risk"),
                generate_mindset_content(topic="psychology"),
            )
            for result in ai_results:
                if result:
                    versions.append(truncate(result))

        if not versions:
            log.error("All AI versions failed to generate")
            await bot.send_message(
                chat_id=config.APPROVAL_GROUP_ID,
                text=f"⚠️ Failed to generate {content_type} content. Please try again manually.",
            )
            return

        # Unique ID for this batch
        uid = uuid.uuid4().hex[:8]

        # ── Send intro message ─────────────────────────────────────────────
        await bot.send_message(
            chat_id=config.APPROVAL_GROUP_ID,
            text=(
                f"🔔 *{label} — Choose a Version*\n\n"
                f"⏰ Auto-sends *Version 1* in 30 minutes if no selection."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

        # ── Version labels per content type ───────────────────────────────
        if content_type == "market":
            version_labels = ["Version 1 — Technical 📊", "Version 2 — Fundamental 📰", "Version 3 — Sentiment 🧠"]
        else:
            version_labels = ["Version 1 — Discipline 🎯", "Version 2 — Risk Mgmt 🛡️", "Version 3 — Psychology 🧘"]

        # ── Send each version with its own button ──────────────────────────
        for i, version in enumerate(versions, 1):
            label = version_labels[i - 1] if i <= len(version_labels) else f"Version {i}"
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"✅ Send {label}",
                    callback_data=f"approve:{uid}:{i}",
                )
            ]])
            await bot.send_message(
                chat_id=config.APPROVAL_GROUP_ID,
                text=f"*━━ {label} ━━*\n\n{version}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            await asyncio.sleep(0.5)  # Avoid Telegram flood limits

        # ── Send skip button ───────────────────────────────────────────────
        skip_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭️ Skip this update", callback_data=f"approve:{uid}:skip")
        ]])
        await bot.send_message(
            chat_id=config.APPROVAL_GROUP_ID,
            text="👆 Tap a version above to post it to the community, or skip.",
            reply_markup=skip_keyboard,
        )

        # ── Schedule 30-min auto-send ──────────────────────────────────────
        task = asyncio.create_task(_auto_send(uid, bot, versions[0]))
        _pending_approvals[uid] = {
            "versions": versions,
            "task": task,
            "sent": False,
        }
        log.info(f"Approval request sent (uid={uid}, {len(versions)} versions, type={content_type})")

    except Exception as e:
        log.error(f"post_for_approval failed: {e}", exc_info=True)


async def _auto_send(uid: str, bot: Bot, version_1: str) -> None:
    """Auto-send Version 1 after 30 minutes if no manual selection was made."""
    await asyncio.sleep(30 * 60)  # 30 minutes

    pending = _pending_approvals.get(uid)
    if not pending or pending["sent"]:
        return  # Already handled manually

    pending["sent"] = True
    _pending_approvals.pop(uid, None)

    try:
        await bot.send_message(
            chat_id=config.MARKET_GROUP_ID,
            text=version_1,
            parse_mode=ParseMode.MARKDOWN,
        )
        await bot.send_message(
            chat_id=config.APPROVAL_GROUP_ID,
            text="⏰ *Auto-sent Version 1* to the community group (30-min timeout reached).",
            parse_mode=ParseMode.MARKDOWN,
        )
        log_message("market_bot", "auto_send", version_1, config.MARKET_GROUP_ID)
        log.info(f"Auto-sent Version 1 for uid={uid}")
    except Exception as e:
        log.error(f"Auto-send failed for uid={uid}: {e}")


async def handle_approval_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle inline button presses from the approval group.
    Callback data format: approve:{uid}:{version_number|skip}
    """
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "approve":
        return

    uid = parts[1]
    choice = parts[2]

    pending = _pending_approvals.get(uid)

    if not pending:
        # Already processed (or expired)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("ℹ️ This update has already been sent or expired.")
        except Exception:
            pass
        return

    if pending["sent"]:
        # Race condition: someone clicked while auto-send was firing
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    # Cancel the 30-min auto-send task
    pending["task"].cancel()
    pending["sent"] = True
    _pending_approvals.pop(uid, None)

    if choice == "skip":
        await query.edit_message_text("⏭️ Update skipped — nothing was sent to the community.")
        log.info(f"Update uid={uid} skipped by {update.effective_user.id}")
        return

    try:
        v_idx = int(choice) - 1
    except ValueError:
        await query.edit_message_text("⚠️ Invalid selection.")
        return

    if v_idx < 0 or v_idx >= len(pending["versions"]):
        await query.edit_message_text("⚠️ Version not found.")
        return

    content = pending["versions"][v_idx]

    try:
        await ctx.bot.send_message(
            chat_id=config.MARKET_GROUP_ID,
            text=content,
            parse_mode=ParseMode.MARKDOWN,
        )
        await query.edit_message_text(f"✅ *Version {choice} sent* to the community group!")
        log_message("market_bot", "approved", content, config.MARKET_GROUP_ID)
        log.info(f"Version {choice} approved and sent (uid={uid}) by {update.effective_user.id}")
    except Exception as e:
        log.error(f"Failed to send approved version uid={uid}: {e}")
        await query.edit_message_text(f"❌ Failed to send: {e}")


# ── Breaking news (direct post — no approval needed) ─────────────────────────

async def check_breaking_news(bot: Bot) -> None:
    """
    Scan for high-impact breaking news and post alerts directly to community.
    Called every 15 minutes by the scheduler.
    """
    if config.BOT_PAUSED:
        return

    try:
        breaking = await check_for_breaking_news(hours_back=1)

        for item in breaking:
            title = item["title"]
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
            await asyncio.sleep(2)

    except Exception as e:
        log.error(f"check_breaking_news failed: {e}", exc_info=True)


async def check_economic_calendar(bot: Bot) -> None:
    """
    Check for upcoming high-impact economic events and alert 30 min before.
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
        "/testnews – Generate 3 market update versions for approval\n"
        "/testmindset – Generate 3 mindset post versions for approval\n"
        "/pause – Pause all scheduled posts\n"
        "/resume – Resume all scheduled posts\n"
        "/stats – View bot statistics\n"
        "/broadcast `<message>` – Send a custom message to the group\n"
        "/help – Show this message\n\n"
        "📅 *Schedule (SGT)*\n"
        "Mon–Fri  07:00, 14:00, 19:00 → Market update\n"
        "Sat–Sun  20:00 → Trading mindset post\n"
        "Both go to approval group first."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_testnews(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger the market update approval flow."""
    await update.message.reply_text("⚙️ Generating 3 market update versions…")
    await post_for_approval(ctx.bot, "market")


@admin_only
async def cmd_testmindset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger the weekend mindset approval flow."""
    await update.message.reply_text("⚙️ Generating 3 mindset post versions…")
    await post_for_approval(ctx.bot, "mindset")


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
    Returns (application, scheduler) — both started by main.py.
    """
    app = Application.builder().token(config.MARKET_BOT_TOKEN).build()

    # Admin commands
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("testnews", cmd_testnews))
    app.add_handler(CommandHandler("testmindset", cmd_testmindset))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # Inline button handler for approval group
    app.add_handler(CallbackQueryHandler(handle_approval_callback, pattern=r"^approve:"))

    # Set up APScheduler
    tz = pytz.timezone(config.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)
    bot = app.bot

    # Market updates: Mon–Fri at 07:00, 14:00, 19:00
    for hour in [7, 14, 19]:
        scheduler.add_job(
            post_for_approval,
            trigger="cron",
            day_of_week="mon-fri",
            hour=hour,
            minute=0,
            args=[bot, "market"],
            id=f"market_update_{hour:02d}h",
            replace_existing=True,
        )

    # Weekend mindset: Sat–Sun at 20:00
    scheduler.add_job(
        post_for_approval,
        trigger="cron",
        day_of_week="sat,sun",
        hour=20,
        minute=0,
        args=[bot, "mindset"],
        id="weekend_mindset",
        replace_existing=True,
    )

    # Breaking news check every 15 minutes (every day)
    scheduler.add_job(
        check_breaking_news,
        trigger="interval",
        minutes=config.NEWS_CHECK_INTERVAL,
        args=[bot],
        id="breaking_news_check",
        replace_existing=True,
    )

    # Economic calendar check every 30 minutes (every day)
    scheduler.add_job(
        check_economic_calendar,
        trigger="interval",
        minutes=30,
        args=[bot],
        id="calendar_check",
        replace_existing=True,
    )

    log.info(
        f"Market bot configured. "
        f"Mon–Fri market updates: 07:00, 14:00, 19:00 {config.TIMEZONE} → approval group. "
        f"Sat–Sun mindset: 20:00 → approval group. "
        f"Approval group: {config.APPROVAL_GROUP_ID}. "
        f"Community group: {config.MARKET_GROUP_ID}."
    )
    return app, scheduler
