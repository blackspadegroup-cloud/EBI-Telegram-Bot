"""
services/intent.py – Intent detection and scoring engine.

Every message that the community bot receives (in DMs or via mention)
is passed through this module BEFORE the AI generates a response.

Intent levels:
  LOW    (1 pt)  – general curiosity, beginner questions
  MEDIUM (2 pts) – learning about trading, asking about Gold/BTC specifically
  HIGH   (3 pts) – asking about accounts, brokers, platforms, deposits, spreads

When a HIGH-intent signal is detected, an alert is immediately sent
to the "EBI Potential Client Update" group.

Soft CTA logic:
  After a HIGH or MEDIUM intent question, the bot appends a soft
  call-to-action line to the AI's answer.
"""

from config import config
from utils.logger import get_logger

log = get_logger("intent")


# ── Intent taxonomy ───────────────────────────────────────────────────────────

# Each entry: (keywords, intent_label, points, send_alert)
INTENT_RULES: list[tuple[list[str], str, int, bool]] = [

    # ── HIGH INTENT — potential client ready to act ───────────────────────────
    (
        ["open account", "opening account", "how to open", "create account",
         "register account", "sign up", "get started", "start trading"],
        "Account Opening", 3, True,
    ),
    (
        ["which broker", "best broker", "recommend broker", "trusted broker",
         "broker for gold", "broker for btc", "broker review", "is this broker safe"],
        "Broker Selection", 3, True,
    ),
    (
        ["minimum deposit", "how much to deposit", "how much to start",
         "how much do i need", "starting capital", "initial deposit"],
        "Deposit Amount", 3, True,
    ),
    (
        ["mt4", "mt5", "metatrader", "trading platform", "which platform",
         "best platform", "mobile trading app", "trading app"],
        "Platform Inquiry", 3, True,
    ),
    (
        ["spread", "commission", "swap", "overnight fee", "trading cost",
         "how much is the fee", "fee to trade"],
        "Trading Costs", 3, True,
    ),
    (
        ["leverage", "margin", "margin call", "how much leverage",
         "1:100", "1:500", "high leverage"],
        "Leverage & Margin", 2, True,
    ),
    (
        ["how to withdraw", "withdrawal", "deposit method", "can i use", "payment method",
         "bank transfer", "crypto deposit", "usdt deposit"],
        "Funding Methods", 3, True,
    ),
    (
        ["demo account", "practice account", "try before", "paper trading",
         "is there a demo"],
        "Demo Account", 2, True,
    ),

    # ── MEDIUM INTENT — engaged learner, warming up ───────────────────────────
    (
        ["how to trade gold", "how to trade xauusd", "how to trade bitcoin",
         "how do i trade", "where to trade", "start trading gold"],
        "How to Trade", 2, False,
    ),
    (
        ["what is lot size", "lot size", "position size", "how many lots",
         "micro lot", "mini lot", "standard lot"],
        "Position Sizing", 2, False,
    ),
    (
        ["stop loss", "take profit", "sl tp", "where to put stop",
         "how to set stop loss"],
        "Risk Management", 2, False,
    ),
    (
        ["technical analysis", "support resistance", "moving average",
         "rsi", "macd", "fibonacci", "chart pattern"],
        "Technical Analysis", 1, False,
    ),
    (
        ["fundamental analysis", "news trading", "economic calendar",
         "how does cpi affect", "why does gold move"],
        "Fundamental Analysis", 1, False,
    ),

    # ── LOW INTENT — general education ───────────────────────────────────────
    (
        ["what is forex", "what is gold trading", "what is xauusd",
         "what is bitcoin", "what is crypto", "what is a pip"],
        "Beginner Education", 1, False,
    ),
]

# ── Soft CTA templates by intent level ────────────────────────────────────────

SOFT_CTA_HIGH = (
    "\n\n💼 Interested in starting live trading? "
    "We work with AIMS FX — a trusted broker with a $100 minimum deposit. "
    "More importantly, our team offers 1-on-1 education to guide you from zero to your first live trade. "
    "Reply here and an admin will reach out to you personally. 🚀"
)

SOFT_CTA_MEDIUM = (
    "\n\n📌 When you're ready to take the next step, our team is here. "
    "We offer 1-on-1 guidance for new traders through AIMS FX — no pressure, just real support. "
    "Feel free to ask an admin anytime."
)


# ── Main detection function ───────────────────────────────────────────────────

def detect_intent(text: str) -> dict | None:
    """
    Scan message text for intent signals.

    Returns a dict if any intent found:
        {
            "label": str,       # e.g. "Account Opening"
            "points": int,      # 1, 2, or 3
            "send_alert": bool, # True for HIGH intent
            "soft_cta": str,    # text to append to AI answer, or ""
        }
    Returns None if no intent detected.
    """
    text_lower = text.lower()
    best: dict | None = None

    for keywords, label, points, send_alert in INTENT_RULES:
        for kw in keywords:
            if kw in text_lower:
                if best is None or points > best["points"]:
                    best = {
                        "label": label,
                        "points": points,
                        "send_alert": send_alert,
                        "soft_cta": SOFT_CTA_HIGH if points >= 3 else (
                            SOFT_CTA_MEDIUM if points == 2 else ""
                        ),
                    }
                break  # Only need one keyword match per rule

    return best


def format_intent_alert(user_id: int, username: str, first_name: str,
                         question: str, label: str, total_score: int) -> str:
    """Format the alert message sent to the Potential Client Update group."""
    display = f"@{username}" if username else first_name
    profile_link = f"tg://user?id={user_id}"

    return (
        f"🎯 *Potential Client Signal*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 [{display}]({profile_link})\n"
        f"🏷️ Intent: *{label}*\n"
        f"📊 Cumulative Score: *{total_score} pts*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Their question:\n"
        f"_{question[:300]}_\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 _Follow up now while interest is hot._"
    )
