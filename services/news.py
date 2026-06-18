"""
services/news.py – Fetch market news from free sources.

Sources (all free, no paid tier needed):
  1. RSS feeds: Reuters, CoinDesk, CoinTelegraph, MarketWatch
  2. NewsAPI (100 req/day free) – optional, improves quality
  3. CryptoPanic (free tier) – crypto news with sentiment
  4. Google News RSS – no API key

Breaking news detection: checks for high-impact keywords.
"""

import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp
import feedparser

from config import config
from utils.logger import get_logger

log = get_logger("news_service")

# ── RSS Feed sources ──────────────────────────────────────────────────────────

GOLD_RSS_FEEDS = [
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.investing.com/rss/market_overview_investing_precious_metals.rss",
    "https://www.kitco.com/rss/news_rss.cfm",
]

CRYPTO_RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]

# Keywords that indicate HIGH IMPACT breaking news
BREAKING_NEWS_KEYWORDS = [
    # US Macro
    "CPI", "consumer price index", "inflation",
    "FOMC", "federal reserve", "fed rate", "interest rate decision",
    "NFP", "nonfarm payroll", "jobs report",
    "GDP", "gross domestic product",
    "PPI", "producer price",
    "unemployment",
    # Geopolitical
    "war", "conflict", "sanctions", "nuclear",
    "recession", "banking crisis", "bank collapse",
    # Crypto specific
    "ETF approval", "ETF rejected", "SEC", "bitcoin ETF",
    "exchange hack", "exchange collapse", "USDT", "stablecoin",
    "whale", "liquidation",
    # Central banks
    "powell", "yellen", "ECB", "bank of england", "BOJ",
    "rate cut", "rate hike", "quantitative easing", "QE",
]

# Keywords indicating gold relevance
GOLD_KEYWORDS = [
    "gold", "xauusd", "xau", "bullion", "precious metal",
    "dollar index", "DXY", "treasury", "yield",
    "fed", "fomc", "inflation", "cpi",
]

# Keywords indicating BTC relevance
BTC_KEYWORDS = [
    "bitcoin", "btc", "crypto", "ethereum", "blockchain",
    "altcoin", "defi", "etf", "coinbase", "binance",
    "whale", "halving", "mining",
]


async def fetch_gold_news(hours_back: int = 6) -> list[dict]:
    """Fetch recent gold/macro news headlines. Returns list of {title, summary, url}."""
    articles = []

    # RSS feeds
    rss_articles = await _fetch_rss_feeds(GOLD_RSS_FEEDS, GOLD_KEYWORDS, hours_back)
    articles.extend(rss_articles)

    # NewsAPI (if key configured)
    if config.NEWS_API_KEY:
        newsapi_articles = await _fetch_newsapi(
            query="gold XAUUSD central bank inflation",
            hours_back=hours_back
        )
        articles.extend(newsapi_articles)

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        key = a["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    log.info(f"Gold news: {len(unique)} articles fetched")
    return unique[:8]  # Top 8


async def fetch_btc_news(hours_back: int = 6) -> list[dict]:
    """Fetch recent Bitcoin/crypto news headlines."""
    articles = []

    # RSS feeds
    rss_articles = await _fetch_rss_feeds(CRYPTO_RSS_FEEDS, BTC_KEYWORDS, hours_back)
    articles.extend(rss_articles)

    # CryptoPanic (if key configured)
    if config.CRYPTOPANIC_API_KEY:
        cp_articles = await _fetch_cryptopanic(hours_back)
        articles.extend(cp_articles)

    # NewsAPI crypto
    if config.NEWS_API_KEY:
        newsapi_articles = await _fetch_newsapi(
            query="bitcoin cryptocurrency BTC ETF",
            hours_back=hours_back
        )
        articles.extend(newsapi_articles)

    # Deduplicate
    seen = set()
    unique = []
    for a in articles:
        key = a["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    log.info(f"BTC news: {len(unique)} articles fetched")
    return unique[:8]


async def check_for_breaking_news(hours_back: int = 1) -> list[dict]:
    """
    Scan recent news for high-impact breaking events.
    Returns list of {title, url, asset} where asset is 'gold', 'bitcoin', or 'both'.
    """
    all_feeds = GOLD_RSS_FEEDS + CRYPTO_RSS_FEEDS
    articles = await _fetch_rss_feeds(all_feeds, BREAKING_NEWS_KEYWORDS, hours_back)

    breaking = []
    for article in articles:
        text = f"{article['title']} {article.get('summary', '')}".lower()
        is_gold = any(kw.lower() in text for kw in GOLD_KEYWORDS)
        is_btc = any(kw.lower() in text for kw in BTC_KEYWORDS)

        if is_gold and is_btc:
            asset = "both"
        elif is_gold:
            asset = "gold"
        elif is_btc:
            asset = "bitcoin"
        else:
            asset = "both"  # General macro affects both

        breaking.append({**article, "asset": asset})

    log.info(f"Breaking news scan: {len(breaking)} high-impact items")
    return breaking


def format_headlines_for_ai(articles: list[dict], max_headlines: int = 5) -> str:
    """Format article list into a clean string for the AI prompt."""
    if not articles:
        return "No recent headlines available."
    lines = []
    for i, a in enumerate(articles[:max_headlines], 1):
        lines.append(f"{i}. {a['title']}")
    return "\n".join(lines)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _fetch_rss_feeds(feed_urls: list, keyword_filter: list, hours_back: int) -> list[dict]:
    """Fetch and parse multiple RSS feeds, filtering by keywords and recency."""
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    async def fetch_one(url: str):
        try:
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            for entry in feed.entries[:10]:
                # Check recency
                published = _parse_rss_date(entry)
                if published and published < cutoff:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")[:300]
                link = entry.get("link", "")

                # Check if relevant
                combined = f"{title} {summary}".lower()
                if keyword_filter and not any(kw.lower() in combined for kw in keyword_filter):
                    continue

                articles.append({
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "published": published,
                    "source": url.split("/")[2] if "/" in url else url,
                })
        except Exception as e:
            log.warning(f"RSS fetch failed for {url}: {e}")

    await asyncio.gather(*[fetch_one(url) for url in feed_urls])
    return articles


async def _fetch_newsapi(query: str, hours_back: int) -> list[dict]:
    """Fetch from NewsAPI (100 req/day on free tier)."""
    from_time = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%S")
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={query}&from={from_time}&sortBy=publishedAt"
        f"&language=en&pageSize=5&apiKey={config.NEWS_API_KEY}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                articles = []
                for a in data.get("articles", []):
                    articles.append({
                        "title": a.get("title", ""),
                        "summary": a.get("description", "")[:300],
                        "url": a.get("url", ""),
                        "source": a.get("source", {}).get("name", "NewsAPI"),
                    })
                return articles
    except Exception as e:
        log.warning(f"NewsAPI fetch failed: {e}")
        return []


async def _fetch_cryptopanic(hours_back: int) -> list[dict]:
    """Fetch from CryptoPanic free API."""
    url = (
        f"https://cryptopanic.com/api/v1/posts/"
        f"?auth_token={config.CRYPTOPANIC_API_KEY}"
        f"&currencies=BTC&filter=important&public=true"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
                articles = []
                for item in data.get("results", []):
                    title = item.get("title", "")
                    articles.append({
                        "title": title,
                        "summary": "",
                        "url": item.get("url", ""),
                        "source": "CryptoPanic",
                    })
                return articles
    except Exception as e:
        log.warning(f"CryptoPanic fetch failed: {e}")
        return []


def _parse_rss_date(entry) -> Optional[datetime]:
    """Try to parse a publish date from an RSS entry."""
    import time
    for field in ["published_parsed", "updated_parsed"]:
        t = getattr(entry, field, None)
        if t:
            try:
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            except Exception:
                pass
    return None
