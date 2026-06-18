"""
services/ai.py – Google Gemini AI service.

Free tier limits:
  - 15 requests per minute
  - 1,000,000 tokens per day
  - Model: gemini-2.0-flash

Sign up at: https://aistudio.google.com/app/apikey
"""

import asyncio
from typing import Optional

from google import genai

from config import config
from utils.logger import get_logger

log = get_logger("ai_service")

# Initialise Gemini client once at import
_client = genai.Client(api_key=config.GEMINI_API_KEY)


async def generate_market_update(gold_data: dict, btc_data: dict) -> Optional[str]:
    """
    Generate a bilingual market update (English + Chinese) for Gold and Bitcoin.

    Returns a formatted Telegram message string, or None on failure.
    """
    prompt = f"""
You are a professional market analyst for a trading community.
Write a concise market update based on the data below.

GOLD (XAUUSD) DATA:
- Current Price: ${gold_data.get('price', 'N/A')}
- 24h Change: {gold_data.get('change_pct', 'N/A')}%
- Recent News Headlines: {gold_data.get('news_headlines', 'No recent news')}

BITCOIN (BTC) DATA:
- Current Price: ${btc_data.get('price', 'N/A')}
- 24h Change: {btc_data.get('change_pct', 'N/A')}%
- Market Cap: ${btc_data.get('market_cap', 'N/A')}
- Recent News Headlines: {btc_data.get('news_headlines', 'No recent news')}

FORMAT YOUR RESPONSE EXACTLY LIKE THIS (use these exact emoji and labels):

🥇 *Gold Update*
[3 sentences max in English covering: macro factors, key driver, sentiment bias]
Bias: [Bullish 📈 / Bearish 📉 / Neutral ➡️]

🥇 *黄金更新*
[Same content in Simplified Chinese, 3 sentences max]
偏向：[做多 📈 / 做空 📉 / 中性 ➡️]

---

₿ *Bitcoin Update*
[3 sentences max in English covering: market move, key driver, sentiment]
Sentiment: [Bullish 📈 / Bearish 📉 / Neutral ➡️]

₿ *比特币更新*
[Same content in Simplified Chinese, 3 sentences max]
情绪：[看多 📈 / 看空 📉 / 中性 ➡️]

RULES:
- Maximum 3 sentences per section
- Be factual, professional, and educational
- Never guarantee profits or give financial advice
- Use simple language that beginners can understand
- Keep it concise — traders are busy
"""
    return await _call_gemini(prompt)


async def generate_breaking_news_alert(headline: str, asset: str) -> Optional[str]:
    """
    Summarize a breaking news headline into a short bilingual alert.
    asset: 'gold', 'bitcoin', or 'both'
    """
    asset_emoji = {"gold": "🥇", "bitcoin": "₿", "both": "🥇₿"}.get(asset, "📰")
    prompt = f"""
You are a market news analyst. A breaking news headline just dropped that affects {asset}.

HEADLINE: {headline}

Write a SHORT bilingual alert for a trading Telegram group.

FORMAT EXACTLY:
🚨 *Breaking Market News* {asset_emoji}

[2 sentences English: what happened + likely market impact]

🚨 *突发市场新闻* {asset_emoji}

[Same in Chinese, 2 sentences]

⚠️ _Stay cautious. Manage your risk._

RULES:
- Be factual, no speculation beyond direct market impact
- Do not give trading advice or profit guarantees
- Keep it under 100 words total
"""
    return await _call_gemini(prompt)


async def answer_trading_question(question: str, context: str = "") -> Optional[str]:
    """
    Answer a trading/community question from a member.
    Returns a friendly, educational response.
    """
    prompt = f"""
You are a friendly AI assistant for "{config.COMMUNITY_NAME}", a trading community focused on Gold (XAUUSD) and Bitcoin.

MEMBER QUESTION: {question}
{f"CONTEXT: {context}" if context else ""}

RULES:
1. Be friendly, patient, and educational
2. Keep the answer concise (3–5 sentences ideally)
3. NEVER guarantee profits or give specific financial advice
4. NEVER recommend buying or selling specific assets
5. Always encourage proper risk management
6. If you don't know something, say so honestly — don't guess
7. If the question is about technical analysis, explain concepts simply
8. Use relevant emojis sparingly to keep it engaging

TOPICS YOU CAN HELP WITH:
- Basic trading education (what is support/resistance, candlesticks, etc.)
- Gold market basics (what moves gold, USD relationship, central banks)
- Bitcoin basics (what it is, how it works, why it's volatile)
- Economic concepts (CPI, FOMC, NFP, interest rates)
- Risk management basics (stop loss, position sizing)
- Community FAQs (how the group works, what the bot does)
- Trading terminology

Respond in the same language the member used. If mixed, respond in English.
"""
    return await _call_gemini(prompt)


async def generate_economic_event_alert(event: dict) -> Optional[str]:
    """Generate a pre-event alert for a high-impact economic release."""
    prompt = f"""
Write a short bilingual alert for a trading community about an upcoming high-impact economic event.

EVENT: {event.get('name', 'Economic Event')}
COUNTRY: {event.get('country', 'US')}
TIME: {event.get('time', 'soon')}
PREVIOUS VALUE: {event.get('previous', 'N/A')}
FORECAST: {event.get('forecast', 'N/A')}

FORMAT EXACTLY:
🚨 *HIGH IMPACT EVENT* 🗓️

📌 {event.get('name', 'Economic Event')} ({event.get('country', 'US')})
⏰ Releasing in ~{event.get('minutes_until', 30)} minutes

[1 sentence: what this event measures and why it matters for Gold/BTC]

🚨 *重要经济事件* 🗓️

[Same info in Chinese]

⚠️ _Expect volatility on Gold and Bitcoin. Manage risk carefully._
⚠️ _黄金和比特币可能出现波动，请谨慎管理风险。_

Keep it under 80 words. Be factual and professional.
"""
    return await _call_gemini(prompt)


# ── Internal helper ───────────────────────────────────────────────────────────

async def _call_gemini(prompt: str, retries: int = 2) -> Optional[str]:
    """Call Gemini API with retry logic. Runs in a thread to keep async."""
    for attempt in range(retries + 1):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: _client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=prompt,
                )
            )
            return response.text.strip()
        except Exception as e:
            log.warning(f"Gemini attempt {attempt + 1} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    log.error("All Gemini retries exhausted")
    return None
