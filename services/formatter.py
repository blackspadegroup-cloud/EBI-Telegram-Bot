"""
services/formatter.py – Message formatting helpers.

Builds the price header block that appears above every AI-generated update.
Also provides formatting utilities used across both bots.
"""

from datetime import datetime
import pytz

from config import config


def format_price_header(gold: dict, btc: dict) -> str:
    """
    Build the price snapshot header shown at the top of each market update.

    Example:
        ─────────────────────────
        🕐 07:02 SGT | Thu 18 Jun
        🥇 Gold   $2,345.60  +0.42%
        ₿  BTC   $67,420     +1.23%
        ─────────────────────────
    """
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M %Z | %a %d %b")

    gold_price = f"${gold['price']:,.2f}"
    gold_change = _format_change(gold["change_pct"])

    btc_price = f"${btc['price']:,.0f}"
    btc_change = _format_change(btc["change_pct"])

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {time_str}\n"
        f"🥇 Gold   {gold_price}   {gold_change}\n"
        f"₿  BTC    {btc_price}   {btc_change}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )


def format_scheduled_post(header: str, ai_content: str, post_type: str = "update") -> str:
    """Combine price header with AI-generated content into a final message."""
    footer = "\n\n_⚠️ Not financial advice. Always manage your risk._"
    return f"{header}{ai_content}{footer}"


def format_welcome_group(username: str, first_name: str, community_name: str) -> str:
    """Public group welcome message for new members."""
    display = f"@{username}" if username else first_name
    return (
        f"🎉 Welcome *{display}* to *{community_name}*!\n\n"
        f"We're glad to have you here. Feel free to ask questions, "
        f"follow market updates, and enjoy the community. 🚀\n\n"
        f"📌 Say hi and introduce yourself!"
    )


def format_welcome_dm(first_name: str, community_name: str) -> str:
    """Private welcome DM sent directly to new members."""
    return (
        f"Hi {first_name}! 👋\n\n"
        f"Welcome to *{community_name}*.\n\n"
        f"I'm your AI assistant. I can help you with:\n"
        f"• 🥇 Gold (XAUUSD) market questions\n"
        f"• ₿ Bitcoin & crypto basics\n"
        f"• 📊 Trading education & terminology\n"
        f"• 🗞️ Economic news explanations\n"
        f"• ❓ Community FAQs\n\n"
        f"Just send me a message anytime and I'll do my best to help.\n\n"
        f"_⚠️ I provide education only — not financial advice._\n\n"
        f"Enjoy your stay! 🚀"
    )


def format_stats(member_count: int, msg_stats_market: dict, msg_stats_community: dict) -> str:
    """Admin stats message."""
    return (
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Members: *{member_count}*\n\n"
        f"📡 *Market Bot* (last 7 days)\n"
        f"   Messages sent: {msg_stats_market.get('count', 0)}\n\n"
        f"💬 *Community Bot* (last 7 days)\n"
        f"   Messages sent: {msg_stats_community.get('count', 0)}\n"
    )


def truncate(text: str, max_len: int = 4096) -> str:
    """Ensure a Telegram message doesn't exceed max length."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 20] + "\n\n_(message truncated)_"


def _format_change(change_pct: float) -> str:
    """Format a percentage change with arrow emoji."""
    if change_pct > 0:
        return f"📈 +{change_pct}%"
    elif change_pct < 0:
        return f"📉 {change_pct}%"
    else:
        return f"➡️ 0.00%"
