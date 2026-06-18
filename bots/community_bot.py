"""
bots/community_bot.py – Bot 2: Community Chat Assistant Bot

Responsibilities:
  - Welcome new members publicly in the group + private DM
  - Answer member questions via AI (trading education, community FAQs)
  - Admin commands: /stats, /help, /broadcast, /pause, /resume
  - Track all members in Supabase

Key behaviors:
  - ONLY responds to direct questions (mentions or DMs), not every message
  - Does not reply to other bots
  - Gracefully handles unanswerable questions
  - Keeps personality: friendly, professional, educational
"""

import asyncio
from telegram import Update, ChatMember, Bot
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
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
)
from services.ai import answer_trading_question
from services.formatter import (
    format_stats,
    format_welcome_dm,
    format_welcome_group,
    truncate,
)
from utils.logger import get_logger

log = get_logger("community_bot")

# Topics the bot explicitly won't engage with
DECLINED_TOPICS = [
    "specific entry", "specific exit", "buy now", "sell now",
    "should i invest", "will it go up", "will it go down",
    "price target", "profit guarantee",
]

# System context injected into every Q&A call
QA_SYSTEM_CONTEXT = f"""
Community: {config.COMMUNITY_NAME}
Focus: Gold (XAUUSD) and Bitcoin trading education
Bot role: Friendly AI assistant — educational only, not financial advice
"""


# ── Admin guard ───────────────────────────────────────────────────────────────

def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ Not authorized.")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


# ── New member welcome ────────────────────────────────────────────────────────

async def handle_chat_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Triggered when a member's status changes.
    Handles: new members joining the group.
    """
    if not update.chat_member:
        return

    old_status = update.chat_member.old_chat_member.status
    new_status = update.chat_member.new_chat_member.status
    user = update.chat_member.new_chat_member.user

    # Only handle: not-member → member transitions
    joined = (
        old_status in (ChatMember.LEFT, ChatMember.BANNED, ChatMember.RESTRICTED)
        and new_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR)
    )

    if not joined or user.is_bot:
        return

    # Save member to database
    upsert_member(
        telegram_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
    )

    log.info(f"New member: {user.first_name} (@{user.username}) ID={user.id}")

    # 1. Public welcome in the group
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
        )
        log_message("community_bot", "welcome_public", group_msg, update.chat_member.chat.id)
    except Exception as e:
        log.error(f"Failed to send public welcome: {e}")

    # 2. Private DM (may fail if user has DMs disabled — that's fine)
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
        # User has privacy settings blocking DMs — not an error
        log.info(f"Could not DM {user.first_name} (privacy settings): {e}")


# ── Message handler (AI Q&A) ──────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming messages:
    - In groups: only respond when mentioned (@BotUsername) or replied to
    - In DMs: always respond
    """
    if not update.message or not update.message.text:
        return

    msg = update.message
    user = msg.from_user

    # Ignore bots
    if user.is_bot:
        return

    # In group chats: only respond if bot is mentioned or message is a reply to bot
    is_private = msg.chat.type == "private"
    is_mentioned = ctx.bot.username and f"@{ctx.bot.username}" in msg.text
    is_reply_to_bot = (
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == ctx.bot.id
    )

    if not is_private and not is_mentioned and not is_reply_to_bot:
        return

    # Clean question (remove bot mention)
    question = msg.text
    if ctx.bot.username:
        question = question.replace(f"@{ctx.bot.username}", "").strip()

    if not question:
        return

    # Check for declined topics
    q_lower = question.lower()
    if any(phrase in q_lower for phrase in DECLINED_TOPICS):
        await msg.reply_text(
            "⚠️ I can't give specific trading signals or financial advice.\n\n"
            "I'm here to educate and explain — not to tell you when to buy or sell. "
            "Always do your own research and manage your risk! 🙏"
        )
        return

    # Show typing indicator
    await ctx.bot.send_chat_action(chat_id=msg.chat_id, action="typing")

    # Generate AI answer
    log.info(f"Q&A from {user.first_name} (ID={user.id}): {question[:80]}")
    answer = await answer_trading_question(question, context=QA_SYSTEM_CONTEXT)

    if not answer:
        answer = (
            "I'm sorry, I couldn't process your question right now. "
            "Please try again in a moment! 🙏"
        )

    await msg.reply_text(truncate(answer), parse_mode=ParseMode.MARKDOWN)
    log_qa(user.id, question, answer)
    log_message("community_bot", "qa", answer, msg.chat_id)


# ── Admin commands ────────────────────────────────────────────────────────────

@admin_only
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 *Community Bot – Admin Commands*\n\n"
        "/stats – View member and message stats\n"
        "/broadcast `<message>` – Announce to the community group\n"
        "/pause – Disable AI responses temporarily\n"
        "/resume – Re-enable AI responses\n"
        "/help – Show this message"
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
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return
    message = " ".join(ctx.args)
    await ctx.bot.send_message(
        chat_id=config.COMMUNITY_GROUP_ID,
        text=f"📢 *Announcement*\n\n{message}",
        parse_mode=ParseMode.MARKDOWN,
    )
    log_message("community_bot", "broadcast", message, config.COMMUNITY_GROUP_ID)
    await update.message.reply_text("✅ Broadcast sent.")


@admin_only
async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    config.BOT_PAUSED = True
    await update.message.reply_text("⏸️ Community bot paused.")


@admin_only
async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    config.BOT_PAUSED = False
    await update.message.reply_text("▶️ Community bot resumed.")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start in DM — show a welcome intro."""
    user = update.effective_user
    upsert_member(user.id, user.username or "", user.first_name or "", user.last_name or "")
    dm_msg = format_welcome_dm(
        first_name=user.first_name or "friend",
        community_name=config.COMMUNITY_NAME,
    )
    await update.message.reply_text(dm_msg, parse_mode=ParseMode.MARKDOWN)


# ── Bot builder ───────────────────────────────────────────────────────────────

def build_community_bot() -> Application:
    """
    Build and configure the Community Bot application.
    Returns the Application — started by main.py.
    """
    app = Application.builder().token(config.COMMUNITY_BOT_TOKEN).build()

    # Welcome new members (requires admin rights in the group + chat_member_updates)
    app.add_handler(ChatMemberHandler(handle_chat_member, ChatMemberHandler.CHAT_MEMBER))

    # Admin commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))

    # AI Q&A — all text messages (group mentions + DMs)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Community bot configured.")
    return app
