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
    perspective: str = "fundamental",
    events: list | None = None,
) -> Optional[str]:
    """
    Generate a bilingual Gold-only market update (English + Chinese).
    perspective: "technical" | "fundamental" | "sentiment"
    events: list of today's high-impact economic events (optional)
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
            "PERSPECTIVE: Fundamental & US-Macro-Driven\n"
            "Focus ONLY on US economic data and macro drivers from the headlines provided:\n"
            "- The key US data or Fed event moving Gold today (CPI, PCE, NFP, jobless claims, GDP, retail sales, FOMC, Fed speakers)\n"
            "- The macro backdrop: USD strength (DXY), Treasury yields, inflation path, Fed rate expectations, risk appetite\n"
            "- Any geopolitical / safe-haven flows supporting or pressuring Gold\n"
            "- Why this specific US fundamental factor matters for Gold right now\n"
            "Reference the actual headlines given. No generic commentary. Gold only — never mention Bitcoin or crypto."
        ),
        "sentiment": (
            "PERSPECTIVE: Market Sentiment & Trader Psychology\n"
            "Focus ONLY on what traders and the crowd are doing with Gold:\n"
            "- Is the market fearful or greedy right now?\n"
            "- Are traders chasing, fading, or sitting on the sidelines?\n"
            "- What traps or opportunities does current sentiment create?\n"
            "- What should a disciplined Gold trader watch for emotionally?\n"
            "Make it feel like a senior trader talking to his team."
        ),
    }

    angle = perspective_instructions.get(perspective, perspective_instructions["fundamental"])

    events_section = ""
    if events:
        event_lines = "\n".join(
            f"- {e.get('name','Event')} ({e.get('country','')}) — "
            f"Previous: {e.get('previous','N/A')}, Forecast: {e.get('forecast','N/A')}"
            for e in events
        )
        events_section = f"\nTODAY'S HIGH-IMPACT ECONOMIC EVENTS 🔴:\n{event_lines}\n(Mention these if they are relevant to Gold's move or outlook.)"

    prompt = f"""You are a professional market analyst for Elite by Infinity, a Gold trading community.
Write a Gold-only market update using the SPECIFIC PERSPECTIVE below. This is one of 3 versions — make it clearly distinct in angle and insight.

{angle}

GOLD (XAUUSD) DATA:
- Current Price: ${gold_data.get('price', 'N/A')}
- 24h Change: {gold_data.get('change_pct', 'N/A')}%
- Recent News Headlines: {gold_data.get('news_headlines', 'No recent news')}
{events_section}

FORMAT YOUR RESPONSE EXACTLY LIKE THIS (no other sections, Gold only):

🥇 *Gold Market Update*
[3 sentences in English — strictly from the assigned perspective. Reference actual price/news/events from the data above.]
Bias: [Bullish 📈 / Bearish 📉 / Neutral ➡️]

🥇 *黄金市场更新*
[Same content in Simplified Chinese, 3 sentences]
偏向：[做多 📈 / 做空 📉 / 中性 ➡️]

RULES:
- Gold ONLY — do not mention Bitcoin or other assets
- Stay strictly in your assigned perspective
- Reference the specific price, headlines, and events provided
- Be factual and professional — never guarantee profits or give financial advice
- Maximum 3 sentences per English section"""
    return await _call_groq(prompt)


async def generate_breaking_news_alert(headline: str, asset: str = "gold") -> Optional[str]:
    """Summarize a breaking Gold / US-macro headline into a short bilingual alert.

    This bot is Gold-only, so `asset` is effectively always "gold"; the
    parameter is kept for backward compatibility.
    """
    prompt = f"""You are a market news analyst for a Gold (XAUUSD) trading community.
A breaking US-macro / Gold headline just dropped.

HEADLINE: {headline}

Write a SHORT bilingual alert for a trading Telegram group, focused on how this
affects GOLD and the US Dollar. Do NOT mention Bitcoin or crypto.

FORMAT EXACTLY:
🚨 *Breaking Market News* 🥇

[2 sentences English: what happened + likely impact on Gold / USD]

🚨 *突发市场新闻* 🥇

[Same in Chinese, 2 sentences]

⚠️ _Stay cautious. Manage your risk._

RULES:
- Gold / US-macro only — never mention Bitcoin, crypto, or other assets
- Be factual, no speculation beyond direct market impact
- Do not give trading advice or profit guarantees
- Keep it under 100 words total"""
    return await _call_groq(prompt)


async def select_top_breaking_news(headlines: list[str], top_n: int = 3) -> list[int]:
    """Ask the AI to rank the most market-moving Gold / US-macro headlines.

    Returns a list of 0-based indices into `headlines`, most important first,
    length <= top_n. Falls back to the first `top_n` items if the AI response
    can't be parsed.
    """
    import re

    if not headlines:
        return []
    if len(headlines) <= top_n:
        return list(range(len(headlines)))

    numbered = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(headlines))
    prompt = f"""You are the senior market analyst for a Gold (XAUUSD) trading community.
From the numbered list of recent Gold / US-macro headlines below, choose the {top_n} MOST
market-moving for GOLD and the US Dollar right now. Prioritise: Fed/rate decisions, US
inflation (CPI/PCE/PPI), jobs data (NFP/jobless claims), GDP, major geopolitical/safe-haven
events, and big USD/Treasury-yield moves. Ignore minor or off-topic items.

HEADLINES:
{numbered}

Respond with ONLY the numbers of your top {top_n} picks, most important FIRST, comma-separated.
Example: 4, 1, 7
No other text, no explanation."""

    response = await _call_groq(prompt)
    if not response:
        return list(range(min(top_n, len(headlines))))

    # Parse integers from the response, keep valid 1-based picks, de-dup, preserve order.
    picks: list[int] = []
    for num in re.findall(r"\d+", response):
        idx = int(num) - 1
        if 0 <= idx < len(headlines) and idx not in picks:
            picks.append(idx)
        if len(picks) >= top_n:
            break

    if not picks:
        return list(range(min(top_n, len(headlines))))
    return picks


async def answer_trading_question(question: str, context: str = "", lang: Optional[str] = None) -> Optional[str]:
    """Answer a trading/community question from a member.

    lang: "en" or "zh" to force the reply language (the member's chosen language).
          None → reply in the same language the member used.
    """
    if lang == "zh":
        language_rule = "Respond ONLY in Simplified Chinese, regardless of the language of the question."
    elif lang == "en":
        language_rule = "Respond ONLY in English, regardless of the language of the question."
    else:
        language_rule = "Respond in the same language the member used. If mixed, respond in English."

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

{language_rule}"""
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

    prompt = f"""You are a professional trading coach for Elite by Infinity, a Gold (XAUUSD) trading community.

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

[1 sentence: what this event measures and why it matters for Gold and the US Dollar]

🚨 *重要经济事件* 🗓️

[Same info in Chinese]

⚠️ _Expect volatility on Gold. Manage risk carefully._
⚠️ _黄金可能出现波动，请谨慎管理风险。_

Keep it under 80 words. Be factual and professional. Focus on Gold/USD only — do not mention Bitcoin or crypto."""
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
