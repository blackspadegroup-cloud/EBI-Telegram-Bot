"""
database.py – Supabase client and all database operations.

Uses existing tables in "The Trading Terminal" Supabase project:
  - telegram_subscribers  : Tracks Telegram community members (existing)
  - telegram_messages     : Inbound/outbound message log (existing)
  - bot_sent_news         : Deduplication hashes for news items (new)
  - bot_state             : Key-value store for runtime state (new)
  - bot_qa_interactions   : Member Q&A history (new)
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional

from supabase import create_client, Client

from config import config
from utils.logger import get_logger

log = get_logger("database")

# ── Client singleton ──────────────────────────────────────────────────────────

_client: Optional[Client] = None


def get_db() -> Client:
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError("Supabase credentials not configured")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


# ── Members ───────────────────────────────────────────────────────────────────
# Uses the existing `telegram_subscribers` table.

def upsert_member(telegram_id: int, username: str, first_name: str, last_name: str = "") -> None:
    """Insert or update a Telegram subscriber record."""
    try:
        get_db().table("telegram_subscribers").upsert({
            "chat_id": telegram_id,
            "username": username or "",
            "first_name": first_name or "",
            "blocked": False,
        }, on_conflict="chat_id").execute()
    except Exception as e:
        log.error(f"upsert_member failed: {e}")


def get_member_count() -> int:
    """Return total number of active (non-blocked) subscribers."""
    try:
        result = (
            get_db().table("telegram_subscribers")
            .select("chat_id", count="exact")
            .eq("blocked", False)
            .execute()
        )
        return result.count or 0
    except Exception as e:
        log.error(f"get_member_count failed: {e}")
        return 0


# ── Message Logs ──────────────────────────────────────────────────────────────
# Uses the existing `telegram_messages` table.

def log_message(bot_name: str, message_type: str, content: str, chat_id: int, success: bool = True) -> None:
    """Log an outbound bot message for auditing."""
    try:
        # Store bot_name+message_type in the 'direction' field as 'out:{bot_name}:{message_type}'
        get_db().table("telegram_messages").insert({
            "chat_id": chat_id,
            "direction": f"out:{bot_name}:{message_type}",
            "text": content[:2000],
        }).execute()
    except Exception as e:
        log.error(f"log_message failed: {e}")


def get_message_stats(bot_name: str, days: int = 7) -> dict:
    """Return message count stats for the last N days."""
    try:
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            get_db().table("telegram_messages")
            .select("id", count="exact")
            .like("direction", f"out:{bot_name}:%")
            .gte("ts", since)
            .execute()
        )
        return {"count": result.count or 0, "days": days}
    except Exception as e:
        log.error(f"get_message_stats failed: {e}")
        return {"count": 0, "days": days}


# ── News Deduplication ────────────────────────────────────────────────────────

def is_news_already_sent(news_text: str) -> bool:
    """Return True if this news item (by hash) was already sent."""
    h = hashlib.md5(news_text[:200].encode()).hexdigest()
    try:
        result = get_db().table("bot_sent_news").select("id").eq("news_hash", h).execute()
        return len(result.data) > 0
    except Exception as e:
        log.error(f"is_news_already_sent failed: {e}")
        return False  # Allow sending on DB error


def mark_news_sent(news_text: str) -> None:
    """Mark a news item as sent to prevent duplicates."""
    h = hashlib.md5(news_text[:200].encode()).hexdigest()
    try:
        get_db().table("bot_sent_news").upsert({"news_hash": h}, on_conflict="news_hash").execute()
    except Exception as e:
        log.error(f"mark_news_sent failed: {e}")


# ── Bot State ─────────────────────────────────────────────────────────────────

def get_state(key: str, default=None):
    """Get a value from the bot_state table."""
    try:
        result = get_db().table("bot_state").select("value").eq("key", key).execute()
        if result.data:
            return result.data[0]["value"]
        return default
    except Exception as e:
        log.error(f"get_state({key}) failed: {e}")
        return default


def set_state(key: str, value) -> None:
    """Upsert a value in the bot_state table."""
    try:
        get_db().table("bot_state").upsert(
            {"key": key, "value": value, "updated_at": datetime.now(timezone.utc).isoformat()},
            on_conflict="key"
        ).execute()
    except Exception as e:
        log.error(f"set_state({key}) failed: {e}")


# ── Q&A Logs ──────────────────────────────────────────────────────────────────

def log_qa(telegram_id: int, question: str, answer: str) -> None:
    """Log a member Q&A interaction."""
    try:
        get_db().table("bot_qa_interactions").insert({
            "telegram_id": telegram_id,
            "question": question[:1000],
            "answer": answer[:2000],
        }).execute()
    except Exception as e:
        log.error(f"log_qa failed: {e}")
