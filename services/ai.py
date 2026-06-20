"""
services/ai.py – Groq AI service.

Free tier limits:
  - 30 requests per minute
  - 14,400 requests per day
  - Model: llama-3.3-70b-versatile

Sign up at: https://console.groq.com
"""

import asyncio
from typing import Optional

from groq import Groq

from config import config
from utils.logger import get_logger

log = get_logger("ai_service")

# Initialise Groq client once at import
_client = Groq(api_key=config.GROQ_API_KEY)


async def generate_market_update(
    gold_data: dict,
    btc_data: dict,
    perspective: str = "balanced",
) -> Optional[str]:
    """
    Generate a bilingual market update (English + Chinese) for Gold and Bitcoin.
    perspective: "technical" | "fundamental" | "sentiment"
    Each perspective produces distinctly different content.
    """

    perspective_instructions = {
        "technical": (
            "PERSPECTIVE: Technical Analysis\n"
            "Focus ONLY on price action and chart behaviour:\n"
            "- Where price is relative to recent highs/lows\n"
            "- Whether momentum is accelerating or stalling\n"
            "- Key price levels traders are watching (support/resistance)\n"
            "- Short-term trend direction based on the move\n"
            "Do NOT discuss news or macro. Pure price-action lens."
        ),
        "fundamental": (
            "PERSPECTIVE: Fundamental & News-Driven\n"
            "Focus ONLY on the news headlines and macro drivers provided:\n"
            "- What specific news or event is moving the market\n"
            "- The macro backdrop (USD, inflation, Fed, risk appetite)\n"
            "- Why this fundamental factor matters for Gold or BTC right now\n"
            "Reference the actual headlines given. No generic commentary."
        ),
        "sentiment": (
            "PERSPECTIVE: Market Sentiment & Trader Psychology\n"
            "Focus ONLY on what traders and the crowd are doing:\n"
            "- Is the market fearful or greedy right now?\n"
            "- Are traders chasing, fading, or sitting on the sidelines?\n"
            "- What traps or opportunities does the current sentiment create?\n"
            "- What should a disciplined trader watch for emotionally?\n"
            "Make it feel like a senior trader talking to his team."
        ),
    }

    angle = perspective_instructions.get(perspective, perspective_instructions["fundamental"])

    prompt = f"""You are a professional market analyst for Elite by Infinity, a trading community.
Write a market update using the SPECIFIC PERSPECTIVE below. This is one of 3 different versions — make it clearly distinct in angle and insight.

{angle}

GOLD (XAUUSD) DATA:
- Current Price: ${gold_data.get('price', 'N/A')}
- 24h Change: {gold_data.get('change_pct', 'N/A')}%
- Recent News Headlines: {gold_data.get('news_headlines', 'No recent news')}

BITCOIN (BTC) DATA:
- Current Price: ${btc_data.get('price', 'N/A')}
- 24h Change: {btc_data.get('change_pct', 'N/A')}%
- Market Cap: ${btc_data.get('market_cap', 'N/A')}
- Recent News Headlines: {btc_data.get('news_headlines', 'No recent news')}

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

🥇 *Gold Update*
[3 sentences in English — strictly from the assigned perspective]
Bias: [Bullish 📈 / Bearish 📉 / Neutral ➡️]

🥇 *黄金更新*
[Same content in Simplified Chinese]
偏向：[做多 📈 / 做空 📉 / 中性 ➡️]

---

₿ *Bitcoin Update*
[3 sentences in English — strictly from the assigned perspective]
Sentiment: [Bullish 📈 / Bearish 📉 / Neutral ➡️]

₿ *比特币更新*
[Same content in Simplified Chinese]
情绪：[看多 📈 / 看空 📉 / 中性 ➡️]

RULES:
- Stay strictly in your assigned perspective — do not blend all three angles
- Reference specific prices and headlines from the data above
- Be factual, professional, never guarantee profits or give financial advice
- Maximum 3 sentences per English section"""
    return await _call_groq(prompt)


async def generate_breaking_news_alert(headline: str, asset: str) -> Optional[str]:
    """Summarize a breaking news headline into a short bilingual alert."""
    asset_emoji = {"gold": "🥇", "bitcoin": "₿", "both": "🥇₿"}.get(asset, "📰")
    prompt = f"""You are a market news analyst. A breaking news headline just dropped that affects {asset}.

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
- Keep it under 100 words total"""
    return await _call_groq(prompt)


async def answer_trading_question(question: str, context: str = "") -> Optional[str]:
    """Answer a trading/community question from a member."""
    prompt = f"""You are a friendly AI assistant for "{config.COMMUNITY_NAME}", a trading community focused on Gold (XAUUSD) and Bitcoin.

MEMBER QUESTION: {question}
{f"CONTEXT: {context}" if context else ""}

RULES:
1. Be friendly, patient, and educational
2. Keep the answer concise (3–5 sentences ideally)
3. NEVER guarantee profits or give specific financial advice
4. NEVER recommend buying or selling specific assets
5. Always encourage proper risk management
6. If you don't know something, say so honestly — don't guess
7. Use relevant emojis sparingly to keep it engaging

Respond in the same language the member used. If mixed, respond in English."""
    return await _call_groq(prompt)


async def generate_mindset_content(topic: str = "discipline") -> Optional[str]:
    """
    Generate weekend trading mindset content — bilingual (EN + CN).
    topic: "discipline" | "risk" | "psychology"
    Each topic produces a distinctly different post.
    """

    topic_instructions = {
        "discipline": (
            "TOPIC: Trading Discipline & Rule-Following\n"
            "Write about the struggle of sticking to your trading plan when emotions kick in.\n"
            "Examples: entering before confirmation, moving stop losses, skipping a valid setup\n"
            "because of a recent loss, or overriding your own rules after a winning streak.\n"
            "Give one specific, concrete action a trader can take this week to improve discipline."
        ),
        "risk": (
            "TOPIC: Risk Management & Position Sizing\n"
            "Write about how traders destroy accounts not from bad entries, but from bad sizing.\n"
            "Examples: doubling down to recover losses, risking 10% on one trade out of conviction,\n"
            "ignoring stop losses, or not accounting for correlated positions.\n"
            "Give one specific rule about risk that every trader should tattoo on their brain."
        ),
        "psychology": (
            "TOPIC: Trading Psychology & Emotional Control\n"
            "Write about a specific emotional trap traders fall into — FOMO, revenge trading,\n"
            "euphoria after a big win, paralysis after a loss, or obsessing over P&L mid-trade.\n"
            "Be raw and honest. Name the emotion, explain exactly why it happens, and give\n"
            "one practical mental technique to handle it in the moment."
        ),
    }

    angle = topic_instructions.get(topic, topic_instructions["discipline"])

    prompt = f"""You are a professional trading coach for Elite by Infinity, a Gold and Bitcoin trading community.

Write a weekend mindset post using the specific topic below. This is one of 3 versions — make it clearly focused on its own angle, not a generic mix.

{angle}

FORMAT YOUR RESPONSE EXACTLY LIKE THIS (no extra text outside this format):

💭 *Weekend Trading Mindset*

[3–4 sentences in English. Be specific, honest, direct. Name a real scenario traders face. Give one concrete takeaway.]

💭 *周末交易心态*

[Same content in Simplified Chinese, 3–4 sentences. Match tone and specifics exactly.]

RULES:
- Stay on the assigned topic — do not blend all three topics into one
- Be direct and blunt, not fluffy or motivational-poster generic
- Reference real trading scenarios (e.g. "after two red days in a row")
- Never guarantee profits or give specific trade advice
- No extra headers, disclaimers, or labels outside the format"""
    return await _call_groq(prompt)


async def generate_economic_event_alert(event: dict) -> Optional[str]:
    """Generate a pre-event alert for a high-impact economic release."""
    prompt = f"""Write a short bilingual alert for a trading community about an upcoming high-impact economic event.

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

Keep it under 80 words. Be factual and professional."""
    return await _call_groq(prompt)


# ── Internal helper ───────────────────────────────────────────────────────────

async def _call_groq(prompt: str, retries: int = 2) -> Optional[str]:
    """Call Groq API with retry logic. Runs in a thread to keep async."""
    for attempt in range(retries + 1):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: _client.chat.completions.create(
                    model=config.GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                    temperature=0.7,
                )
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.warning(f"Groq attempt {attempt + 1} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(2 ** attempt)
    log.error("All Groq retries exhausted")
    return None
