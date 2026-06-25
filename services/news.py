"""
services/news.py – Fetch Gold & US-macro market news from free sources.

Focus: XAUUSD (Gold) and the US economic backdrop that drives it
(Fed policy, inflation, jobs, USD, yields, geopolitics). Bitcoin / crypto
coverage has been intentionally removed from this bot.

Sources (all free, no paid tier needed):
  1. RSS feeds: MarketWatch, Investing.com (precious metals), Kitco,
     FXStreet, plus Google News RSS queries for Gold + US macro
  2. NewsAPI (100 req/day free) – optional, improves quality

Breaking news detection: checks for high-impact US-macro / Gold keywords.
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
    # Core market / precious-metals feeds
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.investing.com/rss/market_overview_investing_precious_metals.rss",
    "https://www.investing.com/rss/news_25.rss",          # Investing.com economic indicators
    "https://www.kitco.com/rss/news_rss.cfm",
    "https://www.fxstreet.com/rss/news",                  # FXStreet – forex & gold
    # Google News RSS queries (no API key) — Gold + US macro focused
    "https://news.google.com/rss/search?q=gold+price+XAUUSD&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Federal+Reserve+OR+%22interest+rate%22+OR+inflation+US&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=US+economy+OR+jobs+report+OR+CPI&hl=en-US&gl=US&ceid=US:en",
]

# Keywords that indicate HIGH IMPACT breaking news (Gold / US-macro only)
BREAKING_NEWS_KEYWORDS = [
    # US inflation & growth data
    "CPI", "core cpi", "consumer price index", "inflation",
    "PCE", "core pce", "PPI", "producer price",
    "GDP", "gross domestic product", "retail sales", "ISM",
    "consumer confidence", "consumer sentiment",
    # Fed / rates
    "FOMC", "federal reserve", "fed minutes", "fed rate",
    "interest rate decision", "rate cut", "rate hike",
    "dot plot", "quantitative easing", "QE", "quantitative tightening",
    # Jobs
    "NFP", "nonfarm payroll", "non-farm payroll", "jobs report",
    "unemployment", "jobless claims", "initial jobless claims", "ADP",
    # USD / yields / fiscal
    "dollar index", "DXY", "treasury", "treasury yield", "bond yield",
    "tariff", "tariffs", "debt ceiling", "government shutdown", "downgrade",
    # Geopolitical / safe-haven drivers
    "war", "conflict", "sanctions", "nuclear", "ceasefire",
    "recession", "banking crisis", "bank collapse", "safe haven",
    # Central bankers / officials
    "powell", "yellen", "bessent", "ECB", "bank of england", "BOJ",
]

# Keywords indicating gold / US-macro relevance
GOLD_KEYWORDS = [
    # Gold itself
    "gold", "xauusd", "xau", "bullion", "precious metal", "safe haven",
    # USD / rates / yields
    "dollar index", "dxy", "us dollar", "treasury", "yield", "real yield",
    # Fed & policy
    "fed", "fomc", "federal reserve", "powell", "rate cut", "rate hike",
    # US data
    "inflation", "cpi", "pce", "ppi", "nonfarm", "payroll", "jobless claims",
    "unemployment", "gdp", "retail sales", "ism", "recession",
    # Macro / geopolitics
    "tariff", "geopolitical", "war", "sanctions", "central bank",
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


async def check_for_breaking_news(hours_back: int = 1) -> list[dict]:
    """
    Scan recent Gold / US-macro news for high-impact breaking events.
    Returns list of {title, url, asset} — asset is always 'gold' (this bot
    is Gold-only; Bitcoin/crypto coverage has been removed).
    """
    articles = await _fetch_rss_feeds(GOLD_RSS_FEEDS, BREAKING_NEWS_KEYWORDS, hours_back)

    breaking = []
    for article in articles:
        breaking.append({**article, "asset": "gold"})

    log.info(f"Breaking news scan: {len(breaking)} high-impact Gold/macro items")
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
