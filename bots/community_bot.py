"""
bots/community_bot.py – Bot 2: Community Chat Assistant Bot

Full feature set:
  ✅ Welcome new members (public + private DM)
  ✅ DM onboarding sequence (Day 0 → 1 → 3 → 5)
  ✅ AI Q&A with intent detection
  ✅ Soft CTA after high/medium intent questions
  ✅ Intent alerts → EBI Potential Client Update group
  ✅ Rules enforcement (warn → warn → auto-mute on 3rd strike)
  ✅ Rate limiting (10 q/hour group, unlimited DM)
  ✅ Weekly engagement content → management group for approval
  ✅ Weekly polls (2 ideas) → management group for approval
  ✅ Milestone DMs (30 days)
  ✅ Re-engagement DMs (21-day dormant)
  ✅ Admin commands: /help /stats /broadcast /announcement /mute /unmute
                     /ban /unban /pause /resume /welcome /reload /testdm
                     /pipeline /start_trading
  ✅ Inline button approval callbacks
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

from config import config
from database import (
    get_member_count,
    get_message_stats,
    log_message,
    log_qa,
    upsert_member,
    is_user_muted,
    is_user_banned,
    mute_user,
    unmute_user,
    ban_user,
    unban_user,
    increment_violations,
    reset_violations,
    add_intent_score,
    log_intent_event,
    get_recent_intent_events,
    get_high_intent_members,
    get_new_members,
)
from services.ai import answer_trading_question
from services.engagement import (
    build_approval_keyboard,
    generate_weekly_content,
    generate_weekly_polls,
    get_pending,
    remove_pending,
    send_for_approval,
    send_milestone_dms,
    send_reengagement_dms,
)
from services.formatter import (
    format_stats,
    format_welcome_dm,
    format_welcome_group,
    truncate,
)
from services.intent import detect_intent, format_intent_alert
from services.onboarding import send_onboarding_step
from utils.logger import get_logger

log = get_logger("community_bot")

# ── Runtime state ─────────────────────────────────────────────────────────────

WELCOME_ENABLED: bool = True

# Rate limiter: { telegram_id: [datetime, ...] }
_rate_tracker: dict[int, list] = defaultdict(list)
RATE_LIMIT_GROUP = 10
RATE_WINDOW_SECONDS = 3600

# ── Content filters ───────────────────────────────────────────────────────────

DECLINED_TOPICS = [
    "specific entry", "specific exit", "buy now", "sell now",
    "should i invest", "will it go up", "will it go down",
    "price target", "profit guarantee",
]

VIOLATION_PATTERNS = [
    "join my group", "join my channel", "follow me", "check my profile",
    "dm me for signals", "i sell signals", "signal group", "free signals",
    "invest with me", "managed account", "guaranteed profit",
    "100% profit", "guaranteed return",
    "send bitcoin", "send btc", "double your", "get rich quick",
    "recovery scam", "crypto recovery",
]

QA_SYSTEM_CONTEXT = f"""
Community: {config.COMMUNITY_NAME}
Focus: Gold (XAUUSD) and Bitcoin trading education
Bot role: Friendly AI assistant — educational only, not financial advice
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_rate_limited(user_id: int) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=RATE_WINDOW_SECONDS)
    _rate_tracker[user_id] = [t for t in _rate_tracker[user_id] if t > cutoff]
    return len(_rate_tracker[user_id]) >= RATE_LIMIT_GROUP


def _record_question(user_id: int) -> None:
    _rate_tracker[user_id].append(datetime.now(timezone.utc))


def _detect_violation(text: str) -> Optional[str]:
    text_lower = text.lower()
    for pattern in VIOLATION_PATTERNS:
        if pattern in text_lower:
            return pattern
    return None


def _welcome_keyboard(bot_username: Optional[str]) -> Optional[InlineKeyboardMarkup]:
    """Deep-link button so new members can start the bot and unblock DMs.

    Telegram forbids bots from DMing users who have never started them. Tapping
    this opens a private chat and fires /start, which sends the welcome DM.
    """
    if not bot_username:
        return None
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "💬 Tap to activate your AI assistant",
            url=f"https://t.me/{bot_username}?start=welcome",
        )
    ]])


async def _notify_admins(bot, message: str) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            log.warning(f"Could not notify admin {admin_id}: {e}")


# ── Admin guard ───────────────────────────────────────────────────────────────

def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ Not authorized.")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Welcome ───────────────────────────────────────────────────────────────────

async def handle_chat_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global WELCOME_ENABLED
    if not update.chat_member:
        return

    old_status = update.chat_member.old_chat_member.status
    new_status = update.chat_member.new_chat_member.status
    user = update.chat_member.new_chat_member.user

    joined = (
        old_status in (ChatMember.LEFT, ChatMember.BANNED, ChatMember.RESTRICTED)
        and new_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR)
    )
    if not joined or user.is_bot:
        return

    upsert_member(
        telegram_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
    )
    log.info(f"New member: {user.first_name} (@{user.username}) ID={user.id}")

    if not WELCOME_ENABLED:
        return

    # Public group welcome
    group_msg = format_welcome_group(
        username=user.username or "",
        first_name=user.first_name or "friend",
        community_name=config.COMMUNITY_NAME,
    )
    try:
        await ctx.bot.send_message(
            chat_id=update.chat_member.chat.id,
            text=group_msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_welcome_keyboard(ctx.bot.username),
        )
        log_message("community_bot", "welcome_public", group_msg, update.chat_member.chat.id)
    except Exception as e:
        log.error(f"Failed to send public welcome: {e}")

    # Private DM (Day 0 of onboarding sequence)
    dm_msg = format_welcome_dm(
        first_name=user.first_name or "friend",
        community_name=config.COMMUNITY_NAME,
    )
    try:
        await ctx.bot.send_message(
            chat_id=user.id,
            text=dm_msg,
            parse_mode=ParseMode.MARKDOWN,
        )
        log_message("community_bot", "welcome_dm", dm_msg, user.id)
    except Exception as e:
        log.info(f"Could not DM {user.first_name} (privacy settings): {e}")


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Full message pipeline:
      1. Basic guards (bot, empty, paused)
      2. Ban check
      3. Rules enforcement (group only)
      4. Group gating (mention / reply-to-bot only)
      5. Mute check
      6. Rate limit (group only)
      7. Declined topic filter
      8. Intent detection → score + alert + soft CTA
      9. AI answer generation
    """
    if not update.message or not update.message.text:
        return

    msg = update.message
    user = msg.from_user

    if user.is_bot or config.BOT_PAUSED:
        return

    text = msg.text
    is_private = msg.chat.type == "private"

    # ── 2. Ban check ──────────────────────────────────────────────────────────
    if is_user_banned(user.id):
        return

    # ── 3. Rules enforcement (group only) ────────────────────────────────────
    if not is_private:
        violation = _detect_violation(text)
        if violation:
            await _handle_violation(update, ctx, user, violation)
            return

    # ── 4. Group gating ───────────────────────────────────────────────────────
    bot_username = (ctx.bot.username or "").lower()
    # Check via entities (most reliable) or plain text fallback
    is_mentioned = False
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "mention":
                mention = text[entity.offset:entity.offset + entity.length].lower()
                if bot_username and mention == f"@{bot_username}":
                    is_mentioned = True
                    break
    if not is_mentioned and bot_username:
        is_mentioned = f"@{bot_username}" in text.lower()

    is_reply_to_bot = (
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == ctx.bot.id
    )
    if not is_private and not is_mentioned and not is_reply_to_bot:
        return

    # ── 5. Mute check ────────────────────────────────────────────────────────
    if is_user_muted(user.id):
        return

    # ── 6. Rate limit (group only) ────────────────────────────────────────────
    if not is_private and _is_rate_limited(user.id):
        await msg.reply_text(
            "⏳ You've asked a lot of questions recently! "
            "Please wait a bit — I want to make sure everyone gets help. 🙏"
        )
        return

    # ── 7. Declined topics ────────────────────────────────────────────────────
    question = text.replace(f"@{ctx.bot.username}", "").strip() if ctx.bot.username else text
    question = question.strip()
    if not question:
        return

    q_lower = question.lower()
    if any(phrase in q_lower for phrase in DECLINED_TOPICS):
        await msg.reply_text(
            "⚠️ I can't give specific trading signals or financial advice.\n\n"
            "I'm here to educate — not to tell you when to buy or sell. "
            "Always do your own research and manage your risk! 🙏"
        )
        return

    # ── 8. Intent detection ───────────────────────────────────────────────────
    intent = detect_intent(question)
    soft_cta = ""

    if intent:
        new_score = add_intent_score(user.id, intent["points"])
        log_intent_event(
            telegram_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            question=question,
            intent_label=intent["label"],
            score=intent["points"],
        )
        soft_cta = intent.get("soft_cta", "")

        # Send alert to EBI Potential Client Update group for HIGH intent
        if intent["send_alert"] and config.POTENTIAL_CLIENT_GROUP_ID:
            alert_text = format_intent_alert(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                question=question,
                label=intent["label"],
                total_score=new_score,
            )
            try:
                await ctx.bot.send_message(
                    chat_id=config.POTENTIAL_CLIENT_GROUP_ID,
                    text=alert_text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as e:
                log.warning(f"Could not send intent alert: {e}")

    # ── 9. AI answer ──────────────────────────────────────────────────────────
    if not is_private:
        _record_question(user.id)

    await ctx.bot.send_chat_action(chat_id=msg.chat_id, action="typing")
    log.info(f"Q&A from {user.first_name} (ID={user.id}): {question[:80]}")

    answer = await answer_trading_question(question, context=QA_SYSTEM_CONTEXT)
    if not answer:
        answer = "I couldn't process your question right now. Please try again in a moment! 🙏"

    # Append soft CTA if applicable
    full_answer = answer + soft_cta if soft_cta else answer

    await msg.reply_text(truncate(full_answer), parse_mode=ParseMode.MARKDOWN)
    log_qa(user.id, question, full_answer)
    log_message("community_bot", "qa", full_answer, msg.chat_id)


# ── Rules enforcement ─────────────────────────────────────────────────────────

async def _handle_violation(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user, violation: str) -> None:
    strikes = increment_violations(user.id)
    display = f"@{user.username}" if user.username else user.first_name
    log.warning(f"Violation by {display} (ID={user.id}): '{violation}' — strike {strikes}")

    if strikes == 1:
        await update.message.reply_text(
            f"⚠️ {display}, please keep the group on-topic and respectful.\n\n"
            f"Spam, self-promotion, and misleading claims are not allowed. "
            f"This is your first warning."
        )
    elif strikes == 2:
        await update.message.reply_text(
            f"🚨 {display}, this is your *final warning*.\n\n"
            f"Further violations will result in being muted. "
            f"Please respect the community rules.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        mute_user(user.id)
        await update.message.reply_text(
            f"🔇 {display} has been muted due to repeated violations. "
            f"Contact an admin if you believe this is a mistake."
        )
        await _notify_admins(
            ctx.bot,
            f"🚨 *Auto-mute triggered*\n\n"
            f"User: {display} (ID: `{user.id}`)\n"
            f"Strikes: {strikes}\n"
            f"Last violation: `{violation}`\n\n"
            f"Use `/unmute {user.id}` to restore access.",
        )


# ── Approval callback handler ─────────────────────────────────────────────────

async def handle_approval_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Approve / Reject button presses from the management group."""
    query = update.callback_query
    await query.answer()

    if not query.data:
        return

    action, approval_id = query.data.split(":", 1)
    pending = get_pending(approval_id)

    if not pending:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⚠️ This approval has already been processed or expired.")
        return

    admin_name = query.from_user.first_name or "Admin"

    if action == "approve":
        try:
            await ctx.bot.send_message(
                chat_id=pending["target_chat_id"],
                text=pending["content"],
                parse_mode=ParseMode.MARKDOWN,
            )
            log_message("community_bot", pending["content_type"], pending["content"], pending["target_chat_id"])
            remove_pending(approval_id)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ Posted to community by {admin_name}.")
            log.info(f"Content approved by {admin_name}, posted to {pending['target_chat_id']}")
        except Exception as e:
            await query.message.reply_text(f"❌ Failed to post: `{e}`", parse_mode=ParseMode.MARKDOWN)

    elif action == "reject":
        remove_pending(approval_id)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"❌ Content rejected by {admin_name}. Nothing was posted.")
        log.info(f"Content rejected by {admin_name}")


# ── Admin commands ────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    upsert_member(user.id, user.username or "", user.first_name or "", user.last_name or "")
    dm_msg = format_welcome_dm(
        first_name=user.first_name or "friend",
        community_name=config.COMMUNITY_NAME,
    )
    await update.message.reply_text(dm_msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_start_trading(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Public command: step-by-step guide to getting started with live trading."""
    user = update.effective_user
    message = (
        f"🚀 *Getting Started with Live Trading*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Here's a simple path to get you from zero to your first trade:\n\n"
        f"*Step 1 — Choose a Regulated Broker* 🏦\n"
        f"Look for brokers regulated by FCA, ASIC, CySEC, or MAS. "
        f"Regulation protects your funds. Ask our admins for trusted recommendations.\n\n"
        f"*Step 2 — Open a Demo Account First* 🎮\n"
        f"Practise with virtual money before risking real capital. "
        f"Most brokers offer free demo accounts with no time limit.\n\n"
        f"*Step 3 — Learn the Basics* 📚\n"
        f"Understand: lot sizes, stop loss, take profit, pip value, and leverage. "
        f"Ask me anything — I'm here to explain.\n\n"
        f"*Step 4 — Fund Your Account* 💳\n"
        f"Start small. Most brokers accept from $100–$500. "
        f"Never deposit money you can't afford to lose.\n\n"
        f"*Step 5 — Risk Management First* 🛡️\n"
        f"Max 1–2% risk per trade. Set your stop loss BEFORE you enter. "
        f"Protect your capital — it's your most important trading tool.\n\n"
        f"*Step 6 — Get Support* 🤝\n"
        f"Our admin team is here to guide you. DM us anytime — "
        f"no pressure, no obligation, just honest help.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_⚠️ Trading involves risk. Never invest more than you can afford to lose._"
    )

    # Trigger a high-intent signal
    if config.POTENTIAL_CLIENT_GROUP_ID:
        alert = format_intent_alert(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            question="/start_trading command used",
            label="Start Trading Guide",
            total_score=add_intent_score(user.id, 3),
        )
        try:
            await ctx.bot.send_message(
                chat_id=config.POTENTIAL_CLIENT_GROUP_ID,
                text=alert,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            log.warning(f"Could not send /start_trading intent alert: {e}")

    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 *Community Bot — Admin Commands*\n\n"
        "*Content*\n"
        "/broadcast `<message>` — Post to community group\n"
        "/announcement `<message>` — Post formatted announcement\n\n"
        "*Moderation*\n"
        "/mute `<user_id>` — Mute a user (internal flag)\n"
        "/unmute `<user_id>` — Unmute a user\n"
        "/ban `<user_id>` — Ban a user (internal flag)\n"
        "/unban `<user_id>` — Unban a user\n\n"
        "*Pipeline*\n"
        "/pipeline — View high-intent potential clients (last 7 days)\n\n"
        "*Settings*\n"
        "/welcome `on|off` — Enable or disable welcome messages\n"
        "/pause — Disable AI Q&A responses\n"
        "/resume — Re-enable AI Q&A responses\n"
        "/reload — Reload admin IDs from env\n\n"
        "*Info & Testing*\n"
        "/stats — View member and message stats\n"
        "/chatid — Show this chat's exact Telegram ID\n"
        "/testwelcome — Fire the welcome flow on yourself (group + DM)\n"
        "/testdm `<user_id>` — Send a test DM to a user\n"
        "/help — Show this message\n\n"
        "*Public Commands*\n"
        "/start\\_trading — Step-by-step guide for new traders"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    member_count = get_member_count()
    market_stats = get_message_stats("market_bot", days=7)
    community_stats = get_message_stats("community_bot", days=7)
    text = format_stats(member_count, market_stats, community_stats)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_pipeline(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command: show high-intent potential clients from the last 7 days."""
    try:
        events = get_recent_intent_events(days=7) or []
        new_members = get_new_members(days=2) or []
        high_intent = get_high_intent_members(min_score=3, days=7) or []

        lines = ["📊 Client Pipeline — Last 7 Days\n"]

        # New members in first 48 hours
        lines.append(f"🆕 New Members (last 48h): {len(new_members)}")
        for m in new_members[:5]:
            display = f"@{m['username']}" if m.get('username') else m.get('first_name', 'Unknown')
            lines.append(f"   • {display}")
        if len(new_members) > 5:
            lines.append(f"   ...and {len(new_members) - 5} more")

        lines.append("")

        # High intent members
        lines.append(f"🎯 High Intent Members (score 3+): {len(high_intent)}")
        for m in high_intent[:8]:
            display = f"@{m['username']}" if m.get('username') else m.get('name', 'Unknown')
            labels = ", ".join(set(m.get('labels', [])))
            lines.append(f"   • {display} — {labels}")

        lines.append("")

        # Recent intent signals
        lines.append(f"📡 Recent Intent Signals: {len(events)}")
        for e in events[:5]:
            display = f"@{e.get('username')}" if e.get('username') else e.get('first_name', 'Unknown')
            question = e.get('question', '')[:80].replace('_', ' ')
            lines.append(f"   • {display}: {e.get('intent_label', '?')}")
            lines.append(f"     \"{question}\"")

        lines.append("\nTip: Use /testdm [user_id] to verify DM access before reaching out.")

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error(f"cmd_pipeline error: {e}")
        await update.message.reply_text(f"Pipeline error: {e}")


@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return
    message = " ".join(ctx.args)
    await ctx.bot.send_message(
        chat_id=config.COMMUNITY_GROUP_ID,
        text=message,
        parse_mode=ParseMode.MARKDOWN,
    )
    log_message("community_bot", "broadcast", message, config.COMMUNITY_GROUP_ID)
    await update.message.reply_text("✅ Broadcast sent.")


@admin_only
async def cmd_announcement(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /announcement Your text here")
        return
    message = " ".join(ctx.args)
    formatted = (
        f"📢 *ANNOUNCEMENT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{message}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_— {config.COMMUNITY_NAME} Team_"
    )
    await ctx.bot.send_message(
        chat_id=config.COMMUNITY_GROUP_ID,
        text=formatted,
        parse_mode=ParseMode.MARKDOWN,
    )
    log_message("community_bot", "announcement", message, config.COMMUNITY_GROUP_ID)
    await update.message.reply_text("✅ Announcement sent.")


@admin_only
async def cmd_mute(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /mute <user_id>")
        return
    try:
        user_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ user_id must be a number.")
        return
    mute_user(user_id)
    await update.message.reply_text(f"🔇 User `{user_id}` muted.", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_unmute(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /unmute <user_id>")
        return
    try:
        user_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ user_id must be a number.")
        return
    unmute_user(user_id)
    reset_violations(user_id)
    await update.message.reply_text(
        f"🔊 User `{user_id}` unmuted and violations reset.",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    try:
        user_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ user_id must be a number.")
        return
    ban_user(user_id)
    await update.message.reply_text(f"🚫 User `{user_id}` banned.", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    try:
        user_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ user_id must be a number.")
        return
    unban_user(user_id)
    reset_violations(user_id)
    await update.message.reply_text(
        f"✅ User `{user_id}` unbanned and violations reset.",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    config.BOT_PAUSED = True
    await update.message.reply_text("⏸️ Community bot paused — AI Q&A disabled.")


@admin_only
async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    config.BOT_PAUSED = False
    await update.message.reply_text("▶️ Community bot resumed — AI Q&A enabled.")


@admin_only
async def cmd_welcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global WELCOME_ENABLED
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        await update.message.reply_text("Usage: /welcome on  or  /welcome off")
        return
    WELCOME_ENABLED = ctx.args[0].lower() == "on"
    status = "enabled ✅" if WELCOME_ENABLED else "disabled ⏸️"
    await update.message.reply_text(f"Welcome messages {status}.")


@admin_only
async def cmd_reload(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    import os
    raw = os.getenv("ADMIN_IDS", "")
    new_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
    config.ADMIN_IDS = new_ids
    await update.message.reply_text(
        f"🔄 Config reloaded.\nAdmin IDs: `{new_ids}`",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def cmd_chatid(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with the current chat's exact Telegram ID and type.

    Run this inside any group to get the correct chat_id (already in the
    -100... supergroup form) for use in your Railway environment variables.
    """
    chat = update.effective_chat
    await update.message.reply_text(
        f"📍 *Chat info*\n"
        f"ID: `{chat.id}`\n"
        f"Type: `{chat.type}`\n"
        f"Title: {chat.title or '—'}",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def cmd_testwelcome(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command: fire the full welcome flow (group post + DM) on yourself.

    Lets you verify the welcome system without needing a real member to join.
    """
    user = update.effective_user
    chat = update.effective_chat

    # Public-style welcome, posted in whatever chat the command was used in
    group_msg = format_welcome_group(
        username=user.username or "",
        first_name=user.first_name or "friend",
        community_name=config.COMMUNITY_NAME,
    )
    await ctx.bot.send_message(
        chat_id=chat.id,
        text=group_msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_welcome_keyboard(ctx.bot.username),
    )

    # Private welcome DM (same as a real join would trigger)
    dm_msg = format_welcome_dm(
        first_name=user.first_name or "friend",
        community_name=config.COMMUNITY_NAME,
    )
    try:
        await ctx.bot.send_message(chat_id=user.id, text=dm_msg, parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ Test welcome sent (group message + DM).")
    except Exception as e:
        await update.message.reply_text(
            f"✅ Group welcome sent.\n⚠️ DM failed: `{e}`\n\n"
            f"Open a DM with the bot and press Start, then try again.",
            parse_mode=ParseMode.MARKDOWN,
        )


@admin_only
async def cmd_testdm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /testdm <user_id>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ user_id must be a number.")
        return
    try:
        await ctx.bot.send_message(
            chat_id=target_id,
            text=(
                f"👋 This is a test message from *{config.COMMUNITY_NAME}* bot.\n\n"
                f"If you received this, DMs are working correctly! ✅"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        await update.message.reply_text(
            f"✅ Test DM sent to `{target_id}`.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to DM `{target_id}`.\nError: `{e}`\n\n"
            f"User may have privacy settings blocking DMs.",
            parse_mode=ParseMode.MARKDOWN,
        )


# ── Bot builder ───────────────────────────────────────────────────────────────

def build_community_bot() -> tuple[Application, AsyncIOScheduler]:
    """
    Build and configure the Community Bot application with all scheduled jobs.
    Returns (Application, AsyncIOScheduler) — both started by main.py.
    """
    app = Application.builder().token(config.COMMUNITY_BOT_TOKEN).build()

    # ── Handlers ──────────────────────────────────────────────────────────────
    app.add_handler(ChatMemberHandler(handle_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_approval_callback, pattern=r"^(approve|reject):"))

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("start_trading", cmd_start_trading))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("pipeline", cmd_pipeline))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("announcement", cmd_announcement))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("reload", cmd_reload))
    app.add_handler(CommandHandler("chatid", cmd_chatid))
    app.add_handler(CommandHandler("testwelcome", cmd_testwelcome))
    app.add_handler(CommandHandler("testdm", cmd_testdm))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ── Scheduler ─────────────────────────────────────────────────────────────
    tz = pytz.timezone(config.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)
    bot = app.bot

    # Onboarding sequence — daily at 09:00
    scheduler.add_job(
        send_onboarding_step, "cron", hour=9, minute=0,
        args=[bot, 1, 1], id="onboarding_day1",
    )
    scheduler.add_job(
        send_onboarding_step, "cron", hour=9, minute=0,
        args=[bot, 3, 3], id="onboarding_day3",
    )
    scheduler.add_job(
        send_onboarding_step, "cron", hour=9, minute=0,
        args=[bot, 5, 5], id="onboarding_day5",
    )

    # Weekly engagement content
    scheduler.add_job(
        generate_weekly_content, "cron", day_of_week="mon", hour=8, minute=0,
        args=[bot, "monday"], id="weekly_monday",
    )
    scheduler.add_job(
        generate_weekly_content, "cron", day_of_week="wed", hour=8, minute=0,
        args=[bot, "wednesday"], id="weekly_wednesday",
    )
    scheduler.add_job(
        generate_weekly_content, "cron", day_of_week="fri", hour=8, minute=0,
        args=[bot, "friday"], id="weekly_friday",
    )
    scheduler.add_job(
        generate_weekly_content, "cron", day_of_week="sat", hour=9, minute=0,
        args=[bot, "weekend"], id="weekly_weekend",
    )

    # Weekly polls — Monday at 08:15 (after Monday content)
    scheduler.add_job(
        generate_weekly_polls, "cron", day_of_week="mon", hour=8, minute=15,
        args=[bot], id="weekly_polls",
    )

    # Milestone DMs — daily at 10:00
    scheduler.add_job(
        send_milestone_dms, "cron", hour=10, minute=0,
        args=[bot], id="milestone_dms",
    )

    # Re-engagement DMs — every Sunday at 11:00
    scheduler.add_job(
        send_reengagement_dms, "cron", day_of_week="sun", hour=11, minute=0,
        args=[bot], id="reengagement_dms",
    )

    log.info("Community bot configured with all scheduled jobs.")
    return app, scheduler
