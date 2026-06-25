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


# ── Onboarding Sequence Tracking ─────────────────────────────────────────────
# Tracks which DM sequence step each member has received.
# Uses bot_state table: key = "onboarding_step:{telegram_id}", value = step number (0–3)

def get_onboarding_step(telegram_id: int) -> int:
    """Return the last completed onboarding step (0 = none sent yet)."""
    return int(get_state(f"onboarding_step:{telegram_id}", 0))


def set_onboarding_step(telegram_id: int, step: int) -> None:
    """Mark that a given onboarding step has been sent."""
    set_state(f"onboarding_step:{telegram_id}", step)


def get_members_for_onboarding(step: int, days_since_join: int) -> list[dict]:
    """
    Return members who joined exactly `days_since_join` days ago
    and have not yet received `step`.
    Uses telegram_subscribers joined_at column.
    """
    try:
        from datetime import timedelta
        target_date = (datetime.now(timezone.utc) - timedelta(days=days_since_join)).date().isoformat()
        result = (
            get_db().table("telegram_subscribers")
            .select("chat_id, first_name")
            .gte("joined_at", f"{target_date}T00:00:00Z")
            .lt("joined_at", f"{target_date}T23:59:59Z")
            .eq("blocked", False)
            .execute()
        )
        members = result.data or []
        # Filter to those who haven't had this step yet
        pending = []
        for m in members:
            current_step = get_onboarding_step(m["chat_id"])
            if current_step < step:
                pending.append(m)
        return pending
    except Exception as e:
        log.error(f"get_members_for_onboarding failed: {e}")
        return []


# ── Intent Scoring ────────────────────────────────────────────────────────────
# Tracks cumulative intent score per member.
# key = "intent_score:{telegram_id}", value = int score

def get_intent_score(telegram_id: int) -> int:
    return int(get_state(f"intent_score:{telegram_id}", 0))


def add_intent_score(telegram_id: int, points: int) -> int:
    """Add points to a member's intent score. Returns new total."""
    current = get_intent_score(telegram_id)
    new_score = current + points
    set_state(f"intent_score:{telegram_id}", new_score)
    return new_score


def log_intent_event(telegram_id: int, username: str, first_name: str,
                     question: str, intent_label: str, score: int) -> None:
    """Log a high-intent interaction for the potential client pipeline."""
    try:
        get_db().table("bot_intent_events").insert({
            "telegram_id": telegram_id,
            "username": username or "",
            "first_name": first_name or "",
            "question": question[:500],
            "intent_label": intent_label,
            "score_delta": score,
        }).execute()
    except Exception as e:
        log.error(f"log_intent_event failed: {e}")


def get_high_intent_members(min_score: int = 5, days: int = 7) -> list[dict]:
    """Return members with intent score >= min_score in the last N days."""
    try:
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            get_db().table("bot_intent_events")
            .select("telegram_id, username, first_name, intent_label, created_at")
            .gte("created_at", since)
            .execute()
        )
        # Aggregate by telegram_id
        from collections import defaultdict
        scores: dict = defaultdict(lambda: {"score": 0, "labels": [], "name": "", "username": ""})
        for row in (result.data or []):
            tid = row["telegram_id"]
            scores[tid]["score"] += 1
            scores[tid]["labels"].append(row["intent_label"])
            scores[tid]["name"] = row["first_name"]
            scores[tid]["username"] = row["username"]
        return [
            {"telegram_id": tid, **data}
            for tid, data in scores.items()
            if data["score"] >= min_score
        ]
    except Exception as e:
        log.error(f"get_high_intent_members failed: {e}")
        return []


def get_recent_intent_events(days: int = 7) -> list[dict]:
    """Return all intent events from the last N days for pipeline view."""
    try:
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            get_db().table("bot_intent_events")
            .select("*")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return result.data or []
    except Exception as e:
        log.error(f"get_recent_intent_events failed: {e}")
        return []


def get_new_members(days: int = 2) -> list[dict]:
    """Return members who joined in the last N days (prime follow-up window)."""
    try:
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            get_db().table("telegram_subscribers")
            .select("chat_id, username, first_name, joined_at")
            .gte("joined_at", since)
            .eq("blocked", False)
            .execute()
        )
        return result.data or []
    except Exception as e:
        log.error(f"get_new_members failed: {e}")
        return []


def get_dormant_members(inactive_days: int = 21) -> list[dict]:
    """
    Return members who have been in the group for 21+ days
    but have zero Q&A interactions in the last 21 days.
    """
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=inactive_days)).isoformat()
        # Get all members who joined before the cutoff
        result = (
            get_db().table("telegram_subscribers")
            .select("chat_id, first_name, username")
            .lt("joined_at", cutoff)
            .eq("blocked", False)
            .execute()
        )
        members = result.data or []

        # Filter out those who have recent Q&A activity
        active_ids_result = (
            get_db().table("bot_qa_interactions")
            .select("telegram_id")
            .gte("created_at", cutoff)
            .execute()
        )
        active_ids = {r["telegram_id"] for r in (active_ids_result.data or [])}
        # Also check who was already re-engaged recently
        return [m for m in members if m["chat_id"] not in active_ids]
    except Exception as e:
        log.error(f"get_dormant_members failed: {e}")
        return []


def get_milestone_members(days_in_group: int = 30) -> list[dict]:
    """Return members who joined exactly `days_in_group` days ago (milestone check)."""
    try:
        from datetime import timedelta
        target_date = (datetime.now(timezone.utc) - timedelta(days=days_in_group)).date().isoformat()
        result = (
            get_db().table("telegram_subscribers")
            .select("chat_id, first_name, username")
            .gte("joined_at", f"{target_date}T00:00:00Z")
            .lt("joined_at", f"{target_date}T23:59:59Z")
            .eq("blocked", False)
            .execute()
        )
        return result.data or []
    except Exception as e:
        log.error(f"get_milestone_members failed: {e}")
        return []


# ── Moderation ────────────────────────────────────────────────────────────────
# Uses bot_state table for mute/ban flags and violation counts.
# Key format: "muted:{telegram_id}", "banned:{telegram_id}", "violations:{telegram_id}"

def is_user_muted(telegram_id: int) -> bool:
    return bool(get_state(f"muted:{telegram_id}", False))


def is_user_banned(telegram_id: int) -> bool:
    return bool(get_state(f"banned:{telegram_id}", False))


def mute_user(telegram_id: int) -> None:
    set_state(f"muted:{telegram_id}", True)


def unmute_user(telegram_id: int) -> None:
    set_state(f"muted:{telegram_id}", False)


def ban_user(telegram_id: int) -> None:
    set_state(f"banned:{telegram_id}", True)


def unban_user(telegram_id: int) -> None:
    set_state(f"banned:{telegram_id}", False)


def get_violations(telegram_id: int) -> int:
    return int(get_state(f"violations:{telegram_id}", 0))


def increment_violations(telegram_id: int) -> int:
    """Increment violation count and return the new total."""
    count = get_violations(telegram_id) + 1
    set_state(f"violations:{telegram_id}", count)
    return count


def reset_violations(telegram_id: int) -> None:
    set_state(f"violations:{telegram_id}", 0)


# ── CRM auto-capture ──────────────────────────────────────────────────────────
# Create or merge a CRM lead from a Telegram interaction. De-dupes by telegram_id,
# keeps the highest score, and logs an activity. Safe: never raises to the caller.

def crm_capture(telegram_id: int, first_name: str = "", username: str = "",
                source: str = "telegram", label: str = "", points: int = 0) -> Optional[int]:
    try:
        db = get_db()
        existing = (
            db.table("crm_leads").select("id,score")
            .eq("telegram_id", telegram_id).limit(1).execute()
        )
        if existing.data:
            lead = existing.data[0]
            new_score = max(int(lead.get("score") or 0), int(points))
            db.table("crm_leads").update({
                "score": new_score,
                "last_activity_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", lead["id"]).execute()
            db.table("crm_activities").insert({
                "lead_id": lead["id"], "type": "signal",
                "summary": f"Telegram: {label or source}", "actor": "telegram-bot",
            }).execute()
            return lead["id"]

        res = db.table("crm_leads").insert({
            "full_name": first_name or f"TG {telegram_id}",
            "telegram_id": telegram_id,
            "source": source,
            "stage": "new", "status": "new",
            "score": int(points),
            "notes": (f"@{username}" if username else ""),
            "dedupe_hash": f"tg:{telegram_id}",
            "created_by": "telegram-bot",
        }).execute()
        lead_id = res.data[0]["id"] if res.data else None
        if lead_id:
            db.table("crm_activities").insert({
                "lead_id": lead_id, "type": "created",
                "summary": f"Lead auto-captured from Telegram: {label or source}",
                "actor": "telegram-bot",
            }).execute()
        return lead_id
    except Exception as e:
        log.error(f"crm_capture failed: {e}")
        return None
