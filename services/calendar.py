"""
services/calendar.py – Economic calendar monitoring.

Source: Forex Factory XML feed (free, no API key required)
URL: https://nfs.faireconomy.media/ff_calendar_thisweek.xml

Monitors HIGH-impact events only (red folder on Forex Factory).
Sends alerts:
  - 30 minutes BEFORE a high-impact event
  - Alert is only sent once per event (tracked in database)
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp
import feedparser
import pytz

from config import config
from database import get_state, set_state
from utils.logger import get_logger

log = get_logger("calendar_service")

FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

# High-impact event keywords
HIGH_IMPACT_EVENTS = [
    "CPI", "Consumer Price Index",
    "FOMC", "Federal Funds Rate", "Fed Rate",
    "NFP", "Non-Farm", "Nonfarm Payroll",
    "GDP", "Gross Domestic Product",
    "PPI", "Producer Price",
    "Unemployment Rate", "Initial Jobless Claims",
    "Retail Sales",
    "ISM",
    "Interest Rate Decision",
    "Core CPI",
    "PCE",
    "Federal Reserve",
    "ECB Rate",
    "Bank of England",
    "BOJ",
]

# Countries that most affect Gold/BTC
RELEVANT_COUNTRIES = ["USD", "EUR", "GBP", "JPY", "CNY", "CHF", "US", "EU"]


async def get_upcoming_high_impact_events(hours_ahead: int = 4) -> list[dict]:
    """
    Return high-impact economic events happening within the next N hours.
    Each event: {name, country, time_utc, time_local, forecast, previous, alert_key}
    """
    events = await _fetch_ff_calendar()
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours_ahead)

    upcoming = []
    for event in events:
        event_time = event.get("time_utc")
        if not event_time:
            continue
        if now < event_time <= cutoff:
            upcoming.append(event)

    return upcoming


async def get_events_to_alert(alert_window_minutes: int = 30) -> list[dict]:
    """
    Return high-impact events that are ~30 minutes away AND haven't been alerted yet.
    Uses database to track sent alerts (key: 'alerted_{event_key}').
    """
    events = await _fetch_ff_calendar()
    now = datetime.now(timezone.utc)

    to_alert = []
    for event in events:
        event_time = event.get("time_utc")
        if not event_time:
            continue

        minutes_until = (event_time - now).total_seconds() / 60

        # Alert window: between 25 and 40 minutes before
        if not (25 <= minutes_until <= 40):
            continue

        # Check if already alerted
        alert_key = f"alerted_{event.get('key', '')}"
        if get_state(alert_key):
            continue

        event["minutes_until"] = round(minutes_until)
        to_alert.append(event)

        # Mark as alerted
        set_state(alert_key, True)
        log.info(f"Scheduled alert for: {event['name']} in ~{round(minutes_until)} min")

    return to_alert


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _fetch_ff_calendar() -> list[dict]:
    """Fetch and parse the Forex Factory calendar XML."""
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, FOREX_FACTORY_URL)

        tz_local = pytz.timezone(config.TIMEZONE)
        events = []

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")

            # Filter to high-impact events only
            if not _is_high_impact(title, summary):
                continue

            time_utc = _parse_ff_date(entry)
            if not time_utc:
                continue

            time_local = time_utc.astimezone(tz_local)
            country = _extract_country(title, summary)

            if country not in RELEVANT_COUNTRIES:
                continue

            # Build unique key for deduplication
            event_key = f"{title[:30]}_{time_utc.strftime('%Y%m%d%H%M')}"

            events.append({
                "name": title,
                "country": country,
                "time_utc": time_utc,
                "time_local": time_local,
                "time_str": time_local.strftime("%H:%M %Z"),
                "forecast": _extract_value(summary, "Forecast"),
                "previous": _extract_value(summary, "Previous"),
                "key": event_key,
            })

        log.info(f"Calendar: {len(events)} high-impact events this week")
        return events

    except Exception as e:
        log.error(f"Calendar fetch failed: {e}")
        return []


def _is_high_impact(title: str, summary: str) -> bool:
    text = f"{title} {summary}".upper()
    return any(kw.upper() in text for kw in HIGH_IMPACT_EVENTS)


def _extract_country(title: str, summary: str) -> str:
    """Try to extract the currency/country code from the event."""
    # Forex Factory typically puts currency in title like "USD CPI"
    words = title.upper().split()
    for country in RELEVANT_COUNTRIES:
        if country in words:
            return country
    return "USD"  # Default to USD


def _extract_value(summary: str, label: str) -> str:
    """Extract Forecast or Previous value from FF summary HTML."""
    import re
    pattern = rf"{label}:?\s*([0-9.%-]+)"
    match = re.search(pattern, summary, re.IGNORECASE)
    return match.group(1) if match else "N/A"


def _parse_ff_date(entry) -> Optional[datetime]:
    """Parse date from Forex Factory feed entry."""
    import time
    for field in ["published_parsed", "updated_parsed"]:
        t = getattr(entry, field, None)
        if t:
            try:
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            except Exception:
                pass
    return None
