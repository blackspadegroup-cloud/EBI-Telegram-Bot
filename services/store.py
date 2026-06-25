"""
services/store.py – DB-backed settings + content cache (Stage 1a foundation).

The admin panel writes content & settings into Supabase; the bots read them here.

Design goals:
  • Bot reads ONLY 'approved' content versions — drafts/pending never go live.
  • Everything is cached in memory and refreshed periodically (and via /reload).
  • SAFE FALLBACK: if Supabase is unreachable or a key is missing, callers fall
    back to the hardcoded defaults shipped in code, so the bot never breaks.

Tables (all created in the bot_admin_foundation migration):
  bot_settings           – key/value (jsonb) admin settings
  bot_content_versions   – versioned message content; bot reads status='approved'
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from config import config
from database import get_db
from utils.logger import get_logger

log = get_logger("store")

# ── In-memory caches (module-level; shared across both bots in one process) ────
_content_cache: dict[tuple[str, str], str] = {}   # (content_key, lang) -> value
_settings_cache: dict[str, Any] = {}              # key -> value
_loaded: bool = False


# ── Reads (sync, cache-only — never hit the network) ──────────────────────────

def get_content(key: str, lang: str = "en") -> Optional[str]:
    """Approved DB content for (key, lang); falls back to en, else None."""
    return _content_cache.get((key, lang)) or _content_cache.get((key, "en"))


def get_setting(key: str, default: Any = None) -> Any:
    return _settings_cache.get(key, default)


def is_paused() -> bool:
    """Global pause flag — DB-backed, falls back to the in-memory config flag."""
    val = _settings_cache.get("paused", None)
    if val is None:
        return bool(config.BOT_PAUSED)
    return bool(val)


def loaded() -> bool:
    return _loaded


# ── Writes ────────────────────────────────────────────────────────────────────

def set_setting(key: str, value: Any, actor: str = "admin") -> None:
    """Upsert a setting and update the local cache immediately."""
    try:
        get_db().table("bot_settings").upsert(
            {
                "key": key,
                "value": value,
                "updated_by": actor,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="key",
        ).execute()
        _settings_cache[key] = value
    except Exception as e:
        log.error(f"set_setting({key}) failed: {e}")


# ── Internal sync fetchers ────────────────────────────────────────────────────

def _fetch_content() -> dict[tuple[str, str], str]:
    res = (
        get_db().table("bot_content_versions")
        .select("content_key,lang,value,version")
        .eq("status", "approved")
        .order("version", desc=True)
        .execute()
    )
    cache: dict[tuple[str, str], str] = {}
    for row in (res.data or []):
        k = (row["content_key"], row["lang"])
        if k not in cache:          # first hit = highest version (ordered desc)
            cache[k] = row["value"]
    return cache


def _fetch_settings() -> dict[str, Any]:
    res = get_db().table("bot_settings").select("key,value").execute()
    return {row["key"]: row["value"] for row in (res.data or [])}


def refresh_sync() -> None:
    """Reload caches from Supabase. Safe: on error, keep the existing cache."""
    global _content_cache, _settings_cache, _loaded
    try:
        content = _fetch_content()
        settings = _fetch_settings()
        # Only swap in if the fetch succeeded (avoids wiping cache on a half-failure)
        _content_cache = content
        _settings_cache = settings
        _loaded = True
        log.info(
            f"store refreshed: {len(_content_cache)} content rows, "
            f"{len(_settings_cache)} settings"
        )
    except Exception as e:
        log.error(f"store refresh failed (keeping existing cache): {e}")


def seed_content_if_empty(strings: dict) -> None:
    """One-time seed of bot_content_versions from the in-code STRINGS table.

    Inserts every (key, lang) pair as an approved v1 — but only if the table is
    currently empty, so it never clobbers content edited via the admin panel.
    """
    try:
        existing = get_db().table("bot_content_versions").select("id").limit(1).execute()
        if existing.data:
            return  # already seeded / has content
        rows = []
        for key, langs in strings.items():
            if not isinstance(langs, dict):
                continue
            for lang, value in langs.items():
                if lang in ("en", "zh") and value:
                    rows.append({
                        "content_key": key,
                        "lang": lang,
                        "value": value,
                        "status": "approved",
                        "version": 1,
                        "created_by": "seed",
                        "reviewed_by": "seed",
                    })
        if rows:
            get_db().table("bot_content_versions").insert(rows).execute()
            log.info(f"Seeded {len(rows)} content rows from code defaults")
    except Exception as e:
        log.error(f"seed_content_if_empty failed: {e}")


# ── Async entry points (run the sync DB work off the event loop) ──────────────

async def initial_load(strings: Optional[dict] = None) -> None:
    """Seed (if empty) then load caches. Call once at startup."""
    loop = asyncio.get_event_loop()
    if strings is not None:
        await loop.run_in_executor(None, seed_content_if_empty, strings)
    await loop.run_in_executor(None, refresh_sync)


async def refresh() -> None:
    """Periodic/manual refresh. Wired to a 60s scheduler job and /reload."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, refresh_sync)
