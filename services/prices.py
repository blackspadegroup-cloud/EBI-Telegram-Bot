"""
services/prices.py – Fetch live price for Gold (XAUUSD).

Uses yfinance (completely free, no API key required) as primary.
yfinance ticker: GC=F (Gold Futures)
"""

import asyncio
from typing import Optional

import yfinance as yf

from utils.logger import get_logger

log = get_logger("prices_service")


async def get_gold_data() -> dict:
    """
    Fetch current Gold (XAUUSD) price and 24h change.
    Returns a dict with: price, change_pct, high, low, volume
    """
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _fetch_gold)
        return data
    except Exception as e:
        log.error(f"get_gold_data failed: {e}")
        return _empty_gold()


# ── Sync fetch helpers (run in thread pool) ───────────────────────────────────

def _fetch_gold() -> dict:
    ticker = yf.Ticker("GC=F")
    info = ticker.fast_info
    hist = ticker.history(period="2d")

    price = round(info.last_price, 2) if hasattr(info, "last_price") else 0.0

    if len(hist) >= 2:
        prev_close = hist["Close"].iloc[-2]
        current = hist["Close"].iloc[-1]
        change_pct = round(((current - prev_close) / prev_close) * 100, 2)
        high = round(hist["High"].iloc[-1], 2)
        low = round(hist["Low"].iloc[-1], 2)
    else:
        change_pct = 0.0
        high = price
        low = price

    result = {
        "price": price,
        "change_pct": change_pct,
        "high": high,
        "low": low,
        "currency": "USD",
        "symbol": "XAUUSD",
    }
    log.info(f"Gold: ${price} ({change_pct:+}%)")
    return result


def _empty_gold() -> dict:
    return {"price": 0.0, "change_pct": 0.0, "high": 0.0, "low": 0.0, "currency": "USD", "symbol": "XAUUSD"}
