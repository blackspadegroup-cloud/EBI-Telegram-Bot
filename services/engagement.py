"""
services/engagement.py – Community engagement automation.

Features:
  1. Weekly engagement content (Monday market outlook, Wednesday tip,
     Friday recap, Weekend mindset) — sent to management group for approval
  2. Weekly poll engine — 2 fun poll ideas sent to management group for approval
  3. Milestone DMs — sent when members hit 30 days in the group
  4. Re-engagement DMs — sent to members dormant for 21+ days

Approval flow (inline buttons):
  Bot sends content to MANAGEMENT_GROUP_ID with [✅ Approve] [❌ Reject] buttons.
  Admin taps Approve → bot posts to COMMUNITY_GROUP_ID.
  Admin taps Reject → bot sends "Content rejected" confirmation, nothing posted.

Pending approvals are stored in memory (dict) keyed by callback_data ID.
They are lost on restart — by design (weekly content is time-sensitive).
"""

import asyncio
import uuid
from datetime import datetime

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from config import config
from services.ai import generate_mindset_content, _call_groq
from utils.logger import get_logger

log = get_logger("engagement")

# ── In-memory pending approvals store ─────────────────────────────────────────
# { approval_id: {"content": str, "target_chat_id": int, "content_type": str} }
_pending_approvals: dict[str, dict] = {}


# ── Approval helpers ──────────────────────────────────────────────────────────

def _store_pending(content: str, target_chat_id: int, content_type: str) -> str:
    """Store content pending approval. Returns unique approval ID."""
    approval_id = str(uuid.uuid4())[:8]
    _pending_approvals[approval_id] = {
        "content": content,
        "target_chat_id": target_chat_id,
        "content_type": content_type,
    }
    return approval_id


def get_pending(approval_id: str) -> dict | None:
    return _pending_approvals.get(approval_id)


def remove_pending(approval_id: str) -> None:
    _pending_approvals.pop(approval_id, None)


def build_approval_keyboard(approval_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve & Post", callback_data=f"approve:{approval_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject:{approval_id}"),
    ]])


async def send_for_approval(bot, content: str, content_type: str,
                             label: str, target_chat_id: int = None) -> None:
    """
    Send content to the management group for approval.
    content_type: "weekly_post", "poll_1", "poll_2", "mindset"
    """
    if not config.MANAGEMENT_GROUP_ID:
        log.warning("MANAGEMENT_GROUP_ID not set — skipping approval flow.")
        return

    dest = target_chat_id or config.COMMUNITY_GROUP_ID
    approval_id = _store_pending(content, dest, content_type)
    keyboard = build_approval_keyboard(approval_id)

    preview = (
        f"📋 *Content Pending Approval* — {label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{content}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Tap Approve to post to the community group, or Reject to discard._"
    )

    try:
        await bot.send_message(
            chat_id=config.MANAGEMENT_GROUP_ID,
            text=preview,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        log.info(f"Sent '{label}' for approval (ID: {approval_id})")
    except Exception as e:
        log.error(f"Failed to send content for approval: {e}")


# ── Weekly engagement content ─────────────────────────────────────────────────

async def generate_weekly_content(bot, day_of_week: str) -> None:
    """
    Generate and submit for approval the scheduled weekly post.
    day_of_week: "monday" | "wednesday" | "friday" | "weekend"
    Called by APScheduler.
    """
    prompts = {
        "monday": (
            "Write a Monday market outlook for a Gold and Bitcoin trading community. "
            "Format: 🗓️ *Week Ahead — Gold & Bitcoin*\n\n"
            "Cover: 3 key economic events this week (use realistic placeholders like 'US CPI Tuesday', 'FOMC Wednesday'), "
            "what traders should watch, and the overall tone for the week. "
            "End with a motivational one-liner for traders. "
            "Bilingual: English first (5–6 sentences), then 中文. Professional and energetic tone."
        ),
        "wednesday": (
            "Write a mid-week trading education tip for a Gold and Bitcoin community. "
            "Format: 📚 *Mid-Week Trading Tip*\n\n"
            "Pick ONE concept from: reading candlestick patterns, understanding market sessions, "
            "using economic calendars, reading order flow, or managing emotions during losses. "
            "Explain it simply in 4–5 sentences with a concrete example. "
            "Bilingual: English first, then 中文. Friendly teacher tone."
        ),
        "friday": (
            "Write a Friday week-in-review post for a Gold and Bitcoin trading community. "
            "Format: 📊 *Week in Review*\n\n"
            "Summarise: how Gold performed this week (use realistic commentary like 'Gold held above key support'), "
            "BTC sentiment, what drove the moves, and what to watch into next week. "
            "Bilingual: English first (5–6 sentences), then 中文. Analytical, calm tone."
        ),
        "weekend": None,  # Uses generate_mindset_content via AI service
    }

    if day_of_week == "weekend":
        import random
        topic = random.choice(["discipline", "risk", "psychology"])
        content = await generate_mindset_content(topic)
        label = "Weekend Mindset Post"
    else:
        prompt = prompts.get(day_of_week)
        if not prompt:
            log.warning(f"Unknown day_of_week: {day_of_week}")
            return
        content = await _call_groq(prompt)
        label = {
            "monday": "Monday Market Outlook",
            "wednesday": "Mid-Week Education Tip",
            "friday": "Friday Week Review",
        }[day_of_week]

    if not content:
        log.error(f"Failed to generate {day_of_week} content.")
        return

    await send_for_approval(bot, content, f"weekly_{day_of_week}", label)


# ── Weekly poll engine ────────────────────────────────────────────────────────

async def generate_weekly_polls(bot) -> None:
    """
    Generate 2 fun poll ideas for the week and send to management group for approval.
    Each poll is sent as a separate message with its own Approve/Reject buttons.
    Called by APScheduler every Monday.
    """
    prompt = """You are a community manager for a Gold and Bitcoin trading group.
Generate 2 FUN and engaging Telegram poll ideas for this week. Mix educational and playful.

Format EXACTLY like this (no extra text):

POLL 1:
Question: [The poll question]
Options:
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D — optional, only if it adds value]

POLL 2:
Question: [The poll question]
Options:
A) [Option A]
B) [Option B]
C) [Option C]

RULES:
- Poll 1 should be market/trading themed (e.g. Gold direction, trader habits)
- Poll 2 should be fun/personality themed (e.g. "What kind of trader are you?", "Which emotion destroys you most?")
- Keep questions short and punchy
- Make options funny where appropriate — traders have a sense of humour
- No financial advice or profit guarantees in any option"""

    raw = await _call_groq(prompt)
    if not raw:
        log.error("Failed to generate weekly polls.")
        return

    # Split into two polls
    parts = raw.strip().split("POLL 2:")
    poll1_text = parts[0].replace("POLL 1:", "").strip() if len(parts) > 0 else ""
    poll2_text = parts[1].strip() if len(parts) > 1 else ""

    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)
    week_label = now.strftime("Week of %d %b %Y")

    if poll1_text:
        content1 = f"📊 *Poll Idea #1 — {week_label}*\n\n{poll1_text}"
        await send_for_approval(bot, content1, "poll_1", "Weekly Poll #1")
        await asyncio.sleep(1)  # Small delay between messages

    if poll2_text:
        content2 = f"🎭 *Poll Idea #2 — {week_label}*\n\n{poll2_text}"
        await send_for_approval(bot, content2, "poll_2", "Weekly Poll #2")


# ── Milestone DMs ─────────────────────────────────────────────────────────────

async def send_milestone_dms(bot) -> None:
    """
    Find members who hit 30 days in the group today and send them a milestone DM.
    Called by APScheduler daily at 10:00.
    """
    from database import get_milestone_members, get_state, set_state

    members = get_milestone_members(days_in_group=30)
    log.info(f"Milestone check: {len(members)} member(s) at 30 days")

    for member in members:
        chat_id = member["chat_id"]
        first_name = member.get("first_name") or "friend"

        # Prevent duplicate sends
        flag_key = f"milestone_30_sent:{chat_id}"
        if get_state(flag_key, False):
            continue

        message = (
            f"Hey {first_name}! 🎉\n\n"
            f"You've been part of *{config.COMMUNITY_NAME}* for a whole month — "
            f"that's awesome! 🥳\n\n"
            f"We hope you've been getting value from the daily market updates and "
            f"community discussions. 📊\n\n"
            f"*Quick question:* Have you had a chance to explore live trading yet? "
            f"If you're curious about getting started or have any questions, "
            f"just reply here — I'm happy to help guide you in the right direction. 💼\n\n"
            f"_Keep learning, stay disciplined, and enjoy the journey!_ 🚀"
        )

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
            )
            set_state(flag_key, True)
            log.info(f"Sent 30-day milestone DM to {first_name} ({chat_id})")
        except Exception as e:
            log.warning(f"Could not send milestone DM to {chat_id}: {e}")


# ── Re-engagement DMs ─────────────────────────────────────────────────────────

async def send_reengagement_dms(bot) -> None:
    """
    Find members dormant for 21+ days and send them a re-engagement DM.
    Called by APScheduler weekly (Sunday at 11:00).
    """
    from database import get_dormant_members, get_state, set_state

    members = get_dormant_members(inactive_days=21)
    log.info(f"Re-engagement check: {len(members)} dormant member(s)")

    # Cap at 20 DMs per run to avoid Telegram rate limits
    for member in members[:20]:
        chat_id = member["chat_id"]
        first_name = member.get("first_name") or "friend"

        # Only re-engage each person once per 30 days
        flag_key = f"reengaged:{chat_id}"
        if get_state(flag_key, False):
            continue

        message = (
            f"Hey {first_name}! 👋\n\n"
            f"It's been a while since we've seen you around *{config.COMMUNITY_NAME}* — "
            f"we miss you! 😊\n\n"
            f"Gold and Bitcoin have been *very active* lately with some major economic "
            f"events moving the markets. Come back and join the conversation! 📊\n\n"
            f"If there's anything you'd like to learn or if you have any questions, "
            f"I'm always here to help. Just send me a message anytime. 🙌\n\n"
            f"_See you in the group!_ 🚀"
        )

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
            )
            set_state(flag_key, True)
            log.info(f"Sent re-engagement DM to {first_name} ({chat_id})")
        except Exception as e:
            log.warning(f"Could not send re-engagement DM to {chat_id}: {e}")
        await asyncio.sleep(0.5)  # Respect Telegram rate limits
