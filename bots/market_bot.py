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

Breaking news runs as a digest 6×/day (daytime SGT: 08, 11, 14, 17, 20, 23):
the AI ranks the 3 most market-moving Gold / US-macro stories and posts all 3
to the management (approval) group. An admin picks 1 of 3 to broadcast; if no
one decides within 10 minutes, the AI's #1 story auto-posts. Quiet windows post
nothing to the community (a short note goes to management). This caps breaking
posts at 6/day. Economic-calendar alerts still post directly (time-sensitive
countdowns).

Admin commands: /testnews, /testbreaking, /testmindset, /pause, /resume,
/stats, /broadcast, /share, /help
"""

import asyncio
import uuid
from datetime import datetime, timedelta
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
    select_top_breaking_news,
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
    fetch_gold_news,
    format_headlines_for_ai,
)
from services.prices import get_gold_data
from services import store
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
    if store.is_paused():
        log.info("Bot is paused — skipping approval request")
        return

    label = "📊 Market Update" if content_type == "market" else "💭 Weekend Mindset"
    log.info(f"Generating 3 versions for approval ({content_type})…")

    try:
        versions = []

        if content_type == "market":
            # Fetch gold price + news + today's high-impact events concurrently
            gold_data, gold_news, events = await asyncio.gather(
                get_gold_data(),
                fetch_gold_news(hours_back=6),
                get_events_to_alert(alert_window_minutes=480),  # events in next 8 hours
            )
            gold_data["news_headlines"] = format_headlines_for_ai(gold_news)
            header = format_price_header(gold_data)

            ai_results = await asyncio.gather(
                generate_market_update(gold_data, perspective="technical", events=events),
                generate_market_update(gold_data, perspective="fundamental", events=events),
                generate_market_update(gold_data, perspective="sentiment", events=events),
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

        # ── Calculate exact post time (30 min from now = scheduled slot) ──
        tz = pytz.timezone(config.TIMEZONE)
        target_time = datetime.now(tz) + timedelta(minutes=30)

        # ── Schedule auto-send at target time ─────────────────────────────
        task = asyncio.create_task(_auto_send(uid, bot, versions[0], target_time))
        _pending_approvals[uid] = {
            "versions": versions,
            "task": task,
            "sent": False,
            "target_time": target_time,
        }
        log.info(f"Approval request sent (uid={uid}, {len(versions)} versions, type={content_type})")

    except Exception as e:
        log.error(f"post_for_approval failed: {e}", exc_info=True)


async def _auto_send(uid: str, bot: Bot, version_1: str, target_time: datetime) -> None:
    """Auto-send Version 1 at the scheduled post time if no manual selection was made."""
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)
    delay = (target_time - now).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)

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
            text=f"⏰ *Auto-sent Version 1* to the community at {target_time.strftime('%H:%M')} SGT (no selection made).",
            parse_mode=ParseMode.MARKDOWN,
        )
        log_message("market_bot", "auto_send", version_1, config.MARKET_GROUP_ID)
        log.info(f"Auto-sent Version 1 for uid={uid} at {target_time.strftime('%H:%M')}")
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
    target_time = pending.get("target_time")

    # Confirm selection immediately
    tz = pytz.timezone(config.TIMEZONE)
    post_time_str = target_time.strftime("%H:%M") if target_time else "now"
    await query.edit_message_text(
        f"✅ *Version {choice} selected!*\n⏰ Posting to community at *{post_time_str} SGT*.",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Wait until the scheduled post time
    if target_time:
        now = datetime.now(tz)
        delay = (target_time - now).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)

    try:
        await ctx.bot.send_message(
            chat_id=config.MARKET_GROUP_ID,
            text=content,
            parse_mode=ParseMode.MARKDOWN,
        )
        await ctx.bot.send_message(
            chat_id=config.APPROVAL_GROUP_ID,
            text=f"📤 *Version {choice} posted* to community at {post_time_str} SGT.",
            parse_mode=ParseMode.MARKDOWN,
        )
        log_message("market_bot", "approved", content, config.MARKET_GROUP_ID)
        log.info(f"Version {choice} approved and posted at {post_time_str} (uid={uid}) by {update.effective_user.id}")
    except Exception as e:
        log.error(f"Failed to send approved version uid={uid}: {e}")
        await ctx.bot.send_message(
            chat_id=config.APPROVAL_GROUP_ID,
            text=f"❌ Failed to post Version {choice}: {e}",
        )


# ── Breaking-news digest (runs 6×/day; admin picks 1 of 3; auto-posts #1) ─────
# uid → { versions: [...], task, sent, approval_chat_id, approval_msg_id }
_pending_breaking: dict = {}

# If no admin picks within this window, the AI's #1 story auto-posts.
BREAKING_AUTO_SEND_SECONDS = 600  # 10 minutes

# How many candidate options to present (admin picks 1).
BREAKING_OPTIONS = 3

# How far back each digest scans for news (covers the gap between runs + margin).
BREAKING_LOOKBACK_HOURS = 5


async def run_breaking_digest(bot: Bot) -> None:
    """
    Breaking-news digest. Runs on a fixed daytime schedule (6×/day).

    1. Scan recent Gold / US-macro news.
    2. Ask the AI to rank the 3 MOST market-moving stories.
    3. Generate a bilingual alert for each and post all 3 to the management
       (approval) group, each with a "Send this one" button.
    4. Admin picks 1 → it posts to the community.
    5. If no decision within BREAKING_AUTO_SEND_SECONDS (10 min), the AI's
       #1 story auto-posts.

    Quiet window: if no significant news is found, nothing goes to the
    community — a short note is sent to the management group instead.
    """
    if store.is_paused():
        log.info("Bot is paused — skipping breaking-news digest")
        return

    try:
        # 1. Gather fresh, not-yet-sent candidates.
        candidates = await check_for_breaking_news(hours_back=BREAKING_LOOKBACK_HOURS)
        fresh = [c for c in candidates if not is_news_already_sent(c["title"])]

        if not fresh:
            await bot.send_message(
                chat_id=config.APPROVAL_GROUP_ID,
                text="🟢 No major Gold / US-macro news this window — nothing sent to the community.",
            )
            log.info("Breaking digest: quiet window, nothing posted")
            return

        # 2. Let the AI rank the most important stories.
        headlines = [c["title"] for c in fresh]
        top_idx = await select_top_breaking_news(headlines, top_n=BREAKING_OPTIONS)
        chosen = [fresh[i] for i in top_idx] if top_idx else fresh[:BREAKING_OPTIONS]

        # 3. Generate an alert for each chosen story (ranked, most important first).
        alerts = await asyncio.gather(
            *[generate_breaking_news_alert(c["title"], c.get("asset", "gold")) for c in chosen]
        )
        versions = [truncate(a) for a in alerts if a]

        if not versions:
            await bot.send_message(
                chat_id=config.APPROVAL_GROUP_ID,
                text="⚠️ Found breaking news but the AI failed to summarise it. Please check manually.",
            )
            log.error("Breaking digest: all AI summaries failed")
            return

        # Mark every presented story as sent so it can't resurface next run.
        for c in chosen[:len(versions)]:
            mark_news_sent(c["title"])

        uid = uuid.uuid4().hex[:8]

        # Intro
        await bot.send_message(
            chat_id=config.APPROVAL_GROUP_ID,
            text=(
                f"🔔 *Breaking News — Pick 1 of {len(versions)}*\n\n"
                f"⏰ Auto-sends *Option 1* (AI's top pick) in 10 minutes if no selection."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

        # Each option with its own button
        for i, version in enumerate(versions, 1):
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"✅ Send Option {i}",
                    callback_data=f"bnews:{uid}:{i}",
                )
            ]])
            await bot.send_message(
                chat_id=config.APPROVAL_GROUP_ID,
                text=f"*━━ Option {i} ━━*\n\n{version}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            await asyncio.sleep(0.5)  # avoid flood limits

        # Skip button
        skip_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭️ Skip — post nothing", callback_data=f"bnews:{uid}:skip")
        ]])
        await bot.send_message(
            chat_id=config.APPROVAL_GROUP_ID,
            text="👆 Tap an option to post it to the community, or skip.",
            reply_markup=skip_keyboard,
        )

        # Schedule the 10-minute auto-send of Option 1.
        task = asyncio.create_task(_auto_send_breaking(uid, bot, versions[0]))
        _pending_breaking[uid] = {
            "versions": versions,
            "task": task,
            "sent": False,
        }
        log.info(f"Breaking digest posted for approval (uid={uid}, {len(versions)} options)")

    except Exception as e:
        log.error(f"run_breaking_digest failed: {e}", exc_info=True)


async def _auto_send_breaking(uid: str, bot: Bot, version_1: str) -> None:
    """Auto-post the AI's #1 story if no admin picks within the timeout."""
    try:
        await asyncio.sleep(BREAKING_AUTO_SEND_SECONDS)
    except asyncio.CancelledError:
        return  # an admin decided in time

    pending = _pending_breaking.get(uid)
    if not pending or pending["sent"]:
        return

    pending["sent"] = True
    _pending_breaking.pop(uid, None)

    try:
        await bot.send_message(
            chat_id=config.MARKET_GROUP_ID,
            text=version_1,
            parse_mode=ParseMode.MARKDOWN,
        )
        log_message("market_bot", "breaking_auto", version_1, config.MARKET_GROUP_ID)
        await bot.send_message(
            chat_id=config.APPROVAL_GROUP_ID,
            text="⏰ Auto-posted *Option 1* to the community (no selection within 10 minutes).",
            parse_mode=ParseMode.MARKDOWN,
        )
        log.info(f"Breaking digest uid={uid} auto-sent Option 1 after timeout")
    except Exception as e:
        log.error(f"Auto-send breaking digest uid={uid} failed: {e}")


async def handle_breaking_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle option selection for a breaking-news digest from the approval group.

    Callback data: bnews:{uid}:{option_number|skip}
    """
    query = update.callback_query
    await query.answer()

    parts = (query.data or "").split(":")
    if len(parts) != 3 or parts[0] != "bnews":
        return

    uid, choice = parts[1], parts[2]
    pending = _pending_breaking.get(uid)

    if not pending or pending["sent"]:
        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("ℹ️ This breaking-news digest was already handled or expired.")
        except Exception:
            pass
        return

    # Stop the 10-minute auto-send timer — an admin is deciding now.
    pending["task"].cancel()
    pending["sent"] = True
    _pending_breaking.pop(uid, None)

    admin = update.effective_user.first_name if update.effective_user else "Admin"

    if choice == "skip":
        await query.edit_message_text(f"⏭️ Breaking news skipped by {admin} — nothing was posted.")
        log.info(f"Breaking digest uid={uid} skipped by {update.effective_user.id}")
        return

    try:
        v_idx = int(choice) - 1
    except ValueError:
        await query.edit_message_text("⚠️ Invalid selection.")
        return

    if v_idx < 0 or v_idx >= len(pending["versions"]):
        await query.edit_message_text("⚠️ Option not found.")
        return

    content = pending["versions"][v_idx]

    try:
        await ctx.bot.send_message(
            chat_id=config.MARKET_GROUP_ID,
            text=content,
            parse_mode=ParseMode.MARKDOWN,
        )
        log_message("market_bot", "breaking", content, config.MARKET_GROUP_ID)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"✅ Option {choice} posted to community by {admin}.")
        log.info(f"Breaking digest uid={uid} Option {choice} posted by {update.effective_user.id}")
    except Exception as e:
        await query.message.reply_text(f"❌ Failed to post: {e}")
        log.error(f"Failed to post breaking Option {choice} uid={uid}: {e}")


async def check_economic_calendar(bot: Bot) -> None:
    """
    Check for upcoming high-impact economic events and alert 30 min before.
    Called every 30 minutes by the scheduler.
    """
    if store.is_paused():
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
        "/testnews – Generate 3 Gold update versions for approval\n"
        "/testbreaking – Run the breaking-news digest now (pick 1 of 3)\n"
        "/testmindset – Generate 3 mindset post versions for approval\n"
        "/share `<url>` [caption] – Share a link to the community group\n"
        "/pause – Pause all scheduled posts\n"
        "/resume – Resume all scheduled posts\n"
        "/stats – View bot statistics\n"
        "/broadcast `<message>` – Send a custom message to the group\n"
        "/help – Show this message\n\n"
        "📅 *Schedule (SGT)*\n"
        "Mon–Fri  06:30, 13:30, 18:30 → Approval versions sent\n"
        "Mon–Fri  07:00, 14:00, 19:00 → Posts to community\n"
        "Sat–Sun  19:30 → Approval versions sent\n"
        "Sat–Sun  20:00 → Posts to community\n\n"
        "🚨 *Breaking News* (daily)\n"
        "08:00, 11:00, 14:00, 17:00, 20:00, 23:00 → AI sends top 3 to pick from\n"
        "Auto-posts Option 1 after 10 min if no pick (max 6 posts/day)"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_testnews(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger the market update approval flow."""
    await update.message.reply_text("⚙️ Generating 3 market update versions…")
    await post_for_approval(ctx.bot, "market")


@admin_only
async def cmd_testbreaking(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually run the breaking-news digest (pick 1 of 3)."""
    await update.message.reply_text("⚙️ Running breaking-news digest…")
    await run_breaking_digest(ctx.bot)


@admin_only
async def cmd_testmindset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger the weekend mindset approval flow."""
    await update.message.reply_text("⚙️ Generating 3 mindset post versions…")
    await post_for_approval(ctx.bot, "mindset")


@admin_only
async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause all automatic posts."""
    config.BOT_PAUSED = True
    store.set_setting("paused", True, actor=str(update.effective_user.id))
    await update.message.reply_text("⏸️ Market bot paused. Use /resume to restart.")
    log.info(f"Bot paused by admin {update.effective_user.id}")


@admin_only
async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume all automatic posts."""
    config.BOT_PAUSED = False
    store.set_setting("paused", False, actor=str(update.effective_user.id))
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


@admin_only
async def cmd_share(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Share a link (Instagram, YouTube, etc.) to the community group.
    Usage: /share <url> [optional caption]
    Example: /share https://www.instagram.com/reel/abc123/ Check out our latest Reel!
    """
    if not ctx.args:
        await update.message.reply_text(
            "Usage: /share <url> [optional caption]\n"
            "Example: /share https://instagram.com/reel/xyz Check out our latest Reel!"
        )
        return

    args = ctx.args
    url = args[0]
    caption = " ".join(args[1:]) if len(args) > 1 else ""

    if caption:
        message = f"📲 {caption}\n\n{url}"
    else:
        message = f"📲 {url}"

    await ctx.bot.send_message(
        chat_id=config.MARKET_GROUP_ID,
        text=message,
        disable_web_page_preview=False,  # Shows link preview (Instagram/YouTube card)
    )
    log_message("market_bot", "share", message, config.MARKET_GROUP_ID)
    await update.message.reply_text("✅ Shared to community group.")


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
    app.add_handler(CommandHandler("testbreaking", cmd_testbreaking))
    app.add_handler(CommandHandler("testmindset", cmd_testmindset))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("share", cmd_share))

    # Inline button handlers for the approval group
    app.add_handler(CallbackQueryHandler(handle_approval_callback, pattern=r"^approve:"))
    app.add_handler(CallbackQueryHandler(handle_breaking_callback, pattern=r"^bnews:"))

    # Set up APScheduler
    tz = pytz.timezone(config.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)
    bot = app.bot

    # Market updates: Mon–Fri, 30 min before post time → approval at 06:30, 13:30, 18:30
    # Community group receives the post at 07:00, 14:00, 19:00
    for hour, minute in [(6, 30), (13, 30), (18, 30)]:
        scheduler.add_job(
            post_for_approval,
            trigger="cron",
            day_of_week="mon-fri",
            hour=hour,
            minute=minute,
            args=[bot, "market"],
            id=f"market_update_{hour:02d}h{minute:02d}",
            replace_existing=True,
        )

    # Weekend mindset: Sat–Sun, approval at 19:30 → posts at 20:00
    scheduler.add_job(
        post_for_approval,
        trigger="cron",
        day_of_week="sat,sun",
        hour=19,
        minute=30,
        args=[bot, "mindset"],
        id="weekend_mindset",
        replace_existing=True,
    )

    # Breaking-news digest 6×/day (daytime-weighted SGT). Each run posts at most
    # one story to the community → max 6 breaking posts per day.
    scheduler.add_job(
        run_breaking_digest,
        trigger="cron",
        hour="8,11,14,17,20,23",
        minute=0,
        args=[bot],
        id="breaking_news_digest",
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
        f"Approval sent at 06:30/13:30/18:30, posts to community at 07:00/14:00/19:00 (Mon–Fri). "
        f"Weekend mindset approval at 19:30, posts at 20:00 (Sat–Sun). "
        f"Timezone: {config.TIMEZONE}."
    )
    return app, scheduler
