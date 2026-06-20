"""
config.py – Central configuration loaded from .env
All other modules import from here, never from os.environ directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Telegram ─────────────────────────────────────────────
    MARKET_BOT_TOKEN: str = os.getenv("MARKET_BOT_TOKEN", "")
    COMMUNITY_BOT_TOKEN: str = os.getenv("COMMUNITY_BOT_TOKEN", "")
    MARKET_GROUP_ID: int = int(os.getenv("MARKET_GROUP_ID", "0"))
    COMMUNITY_GROUP_ID: int = int(os.getenv("COMMUNITY_GROUP_ID", "0"))
    ADMIN_IDS: list[int] = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]

    # ── AI ────────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"  # Free tier model

    # ── Special Groups ────────────────────────────────────────
    # "EBI Bot Management" — weekly content + polls sent here for approval
    MANAGEMENT_GROUP_ID: int = int(os.getenv("MANAGEMENT_GROUP_ID", "0"))
    # "EBI Potential Client Update" — intent scoring alerts go here
    POTENTIAL_CLIENT_GROUP_ID: int = int(os.getenv("POTENTIAL_CLIENT_GROUP_ID", "0"))

    # ── Database ──────────────────────────────────────────────
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # ── News APIs ─────────────────────────────────────────────
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    CRYPTOPANIC_API_KEY: str = os.getenv("CRYPTOPANIC_API_KEY", "")

    # ── Scheduling ────────────────────────────────────────────
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Singapore")
    # Hours (in local timezone) to post market updates
    SCHEDULE_HOURS: list[int] = [7, 14, 19]
    # Minutes interval to check for breaking news
    NEWS_CHECK_INTERVAL: int = int(os.getenv("NEWS_CHECK_INTERVAL", "15"))
    # How far back to scan for breaking news (hours)
    NEWS_LOOKBACK_HOURS: int = int(os.getenv("NEWS_LOOKBACK_HOURS", "2"))

    # ── Community ─────────────────────────────────────────────
    COMMUNITY_NAME: str = os.getenv("COMMUNITY_NAME", "Elite by Infinity")

    # ── Runtime state (mutable) ───────────────────────────────
    # Set to True via /pause command to stop posting
    BOT_PAUSED: bool = False

    def validate(self) -> None:
        """Raise if any required value is missing."""
        required = {
            "MARKET_BOT_TOKEN": self.MARKET_BOT_TOKEN,
            "COMMUNITY_BOT_TOKEN": self.COMMUNITY_BOT_TOKEN,
            "MARKET_GROUP_ID": self.MARKET_GROUP_ID,
            "COMMUNITY_GROUP_ID": self.COMMUNITY_GROUP_ID,
            "GROQ_API_KEY": self.GROQ_API_KEY,
            "SUPABASE_URL": self.SUPABASE_URL,
            "SUPABASE_KEY": self.SUPABASE_KEY,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


config = Config()
