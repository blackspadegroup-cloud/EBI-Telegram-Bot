"""
services/onboarding.py – DM onboarding sequence for new members.

Sequence schedule (relative to join date):
  Day 0 – Immediate welcome DM (sent by community_bot.py handle_chat_member)
  Day 1 – "Gold trading in 60 seconds" education piece
  Day 3 – "#1 mistake new traders make" hook + risk tip
  Day 5 – Soft conversion CTA: "Ready to take the next step?"

APScheduler jobs (registered in build_community_bot):
  send_onboarding_day1  – runs daily at 09:00, finds Day-1 members
  send_onboarding_day3  – runs daily at 09:00, finds Day-3 members
  send_onboarding_day5  – runs daily at 09:00, finds Day-5 members

Each job:
  1. Queries DB for members at that milestone who haven't received the step yet
  2. Sends the DM
  3. Marks the step as sent so it never re-sends
"""

from config import config
from utils.logger import get_logger

log = get_logger("onboarding")


# ── Message templates ─────────────────────────────────────────────────────────

def msg_day1(first_name: str) -> str:
    return (
        f"Hey {first_name}! 👋\n\n"
        f"*Gold trading in 60 seconds* 🥇\n\n"
        f"Gold (XAUUSD) moves based on 3 key forces:\n\n"
        f"1️⃣ *The US Dollar* — When USD weakens, Gold rises (they move opposite)\n"
        f"2️⃣ *Interest rates* — Lower rates = Gold becomes more attractive vs bonds\n"
        f"3️⃣ *Global fear* — War, crisis, uncertainty → investors rush into Gold\n\n"
        f"That's why every major news event (CPI, FOMC, NFP) moves Gold — "
        f"they all affect the dollar and interest rate expectations.\n\n"
        f"Tomorrow when you see Gold moving, ask yourself: *which of these 3 is driving it?*\n\n"
        f"_More tips coming soon. Stay sharp! 📈_"
    )


def msg_day3(first_name: str) -> str:
    return (
        f"Hey {first_name} 👋\n\n"
        f"*The #1 mistake new Gold traders make* 🚨\n\n"
        f"It's not a bad entry. It's not the wrong direction.\n\n"
        f"It's *trading without a stop loss.*\n\n"
        f"Here's why it destroys accounts:\n"
        f"Gold can move 200–500 pips in a single news event. Without a stop loss, "
        f"one wrong trade can wipe out weeks of gains in minutes.\n\n"
        f"*The rule every professional follows:*\n"
        f"➡️ Never risk more than 1–2% of your account on a single trade.\n"
        f"➡️ Set your stop loss BEFORE you enter. Not after.\n"
        f"➡️ If you can't define your risk, don't take the trade.\n\n"
        f"Risk management isn't boring — it's what keeps you in the game long enough to profit.\n\n"
        f"_Have questions about risk management? Just reply here — I'm happy to explain more._ 🙏"
    )


def msg_day5(first_name: str) -> str:
    return (
        f"Hey {first_name}! 👋\n\n"
        f"You've been in the *{config.COMMUNITY_NAME}* community for 5 days now — "
        f"hope you've been finding value in the daily updates! 🙌\n\n"
        f"*Thinking about taking the next step?* 🚀\n\n"
        f"If you're ready to move from learning to live trading, here's what most beginners want to know:\n\n"
        f"✅ You can start with a small amount — most brokers allow deposits from $100–$500\n"
        f"✅ Demo accounts let you practise with zero risk before going live\n"
        f"✅ Our team can guide you through choosing a trusted, regulated broker\n"
        f"✅ We don't charge for guidance — your success is our reputation\n\n"
        f"*Ready to explore?* Just reply to this message or DM one of our admins in the group. "
        f"No pressure, no obligation — just an honest conversation. 💼\n\n"
        f"_Whatever you decide, we're here to support your trading journey._ 🥇"
    )


# ── Scheduler job functions ───────────────────────────────────────────────────

async def send_onboarding_step(bot, step: int, days_since_join: int) -> None:
    """
    Find all members at `days_since_join` who haven't received `step` yet,
    and send them the appropriate DM.

    Called by APScheduler — do not call directly from message handlers.
    """
    from database import get_members_for_onboarding, set_onboarding_step

    message_fn = {1: msg_day1, 3: msg_day3, 5: msg_day5}.get(step)
    if not message_fn:
        return

    members = get_members_for_onboarding(step=step, days_since_join=days_since_join)
    log.info(f"Onboarding step {step}: {len(members)} members eligible")

    for member in members:
        chat_id = member["chat_id"]
        first_name = member.get("first_name") or "friend"
        try:
            from telegram.constants import ParseMode
            await bot.send_message(
                chat_id=chat_id,
                text=message_fn(first_name),
                parse_mode=ParseMode.MARKDOWN,
            )
            set_onboarding_step(chat_id, step)
            log.info(f"Sent onboarding step {step} to {first_name} ({chat_id})")
        except Exception as e:
            log.warning(f"Could not send onboarding step {step} to {chat_id}: {e}")
