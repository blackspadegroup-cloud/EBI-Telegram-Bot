"""
main.py – Entry point for EBI Telegram Bots.

Starts both bots concurrently using asyncio:
  - Bot 1: Market Analysis Bot (with APScheduler)
  - Bot 2: Community Assistant Bot

Both bots run in the same process using python-telegram-bot's
native async support. Each bot polls Telegram independently.

Usage:
    python main.py
"""

import asyncio
import signal
import sys

from telegram import Update

from config import config
from utils.logger import get_logger
from bots.market_bot import build_market_bot
from bots.community_bot import build_community_bot

log = get_logger("main")


async def run_all() -> None:
    """Initialize and run both bots + scheduler concurrently."""

    # Validate all required env vars before starting
    try:
        config.validate()
    except ValueError as e:
        log.error(f"Configuration error: {e}")
        log.error("Please copy .env.example to .env and fill in all required values.")
        sys.exit(1)

    log.info("=" * 50)
    log.info(f"Starting EBI Telegram Bots")
    log.info(f"Community: {config.COMMUNITY_NAME}")
    log.info(f"Timezone: {config.TIMEZONE}")
    log.info(f"Schedule hours: {config.SCHEDULE_HOURS}")
    log.info(f"Admin IDs: {config.ADMIN_IDS}")
    log.info("=" * 50)

    # Load DB-backed settings + content into the in-memory store (Stage 1a).
    # Seeds bot_content_versions from the in-code STRINGS table on first run,
    # then loads approved content + settings. Safe: on any DB error the bots
    # fall back to the hardcoded defaults.
    from services import store
    from services.i18n import STRINGS
    await store.initial_load(STRINGS)

    # Build both bots (both return (Application, AsyncIOScheduler))
    market_app, market_scheduler = build_market_bot()
    community_app, community_scheduler = build_community_bot()

    # Graceful shutdown handler
    shutdown_event = asyncio.Event()

    def handle_signal(*_):
        log.info("Shutdown signal received...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_event_loop().add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # Start both schedulers
    market_scheduler.start()
    community_scheduler.start()
    log.info("APSchedulers started (market + community)")

    # Initialize both bot applications
    await market_app.initialize()
    await community_app.initialize()

    # Start both bots (begin polling)
    await market_app.start()
    await community_app.start()

    # NOTE: Telegram does NOT deliver `chat_member` updates by default — they must
    # be explicitly requested via allowed_updates. The community bot relies on these
    # to detect new members and send welcome messages, so we opt into ALL update types.
    await market_app.updater.start_polling(drop_pending_updates=True)
    await community_app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

    log.info("✅ Both bots are running. Press Ctrl+C to stop.")

    # Wait until shutdown signal
    await shutdown_event.wait()

    # Graceful shutdown
    log.info("Shutting down bots...")
    market_scheduler.shutdown(wait=False)
    community_scheduler.shutdown(wait=False)
    await market_app.updater.stop()
    await community_app.updater.stop()
    await market_app.stop()
    await community_app.stop()
    await market_app.shutdown()
    await community_app.shutdown()
    log.info("All bots stopped. Goodbye.")


if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        log.info("Keyboard interrupt — exiting.")
