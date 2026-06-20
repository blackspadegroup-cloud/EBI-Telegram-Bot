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
        f"Gold trading in 60 seconds 🥇\n\n"
        f"Gold (XAUUSD) moves on 3 key forces:\n\n"
        f"1. The US Dollar — When USD weakens, Gold rises. They move opposite.\n"
        f"2. Interest rates — Lower rates make Gold more attractive than bonds.\n"
        f"3. Global fear — War, crisis, uncertainty drives investors into Gold as a safe haven.\n\n"
        f"This is why every major news event — CPI, FOMC, NFP — moves Gold. "
        f"They all affect the dollar and rate expectations.\n\n"
        f"Next time you see Gold moving, ask yourself: which of these 3 is driving it?\n\n"
        f"That simple question will make you a sharper trader than 90% of beginners.\n\n"
        f"More coming on Day 3. Stay disciplined. 📈\n"
        f"— Elite by Infinity"
    )


def msg_day3(first_name: str) -> str:
    return (
        f"Hey {first_name} 👋\n\n"
        f"The #1 mistake new traders make — and it's not a bad entry. 🚨\n\n"
        f"It's trading without a stop loss.\n\n"
        f"Gold can move 300–500 pips in a single news event. "
        f"Without a stop loss, one wrong trade can wipe out weeks of gains in minutes. "
        f"We've seen it happen to good traders.\n\n"
        f"The rule every professional lives by:\n"
        f"➡️ Never risk more than 1–2% of your account on a single trade\n"
        f"➡️ Set your stop loss BEFORE you enter — not after\n"
        f"➡️ If you can't define your risk, you're not trading. You're gambling.\n\n"
        f"Risk management isn't the boring part. It's what keeps you alive long enough to profit.\n\n"
        f"Questions? Just reply here — I'm happy to go deeper on any of this. 🙏\n"
        f"— Elite by Infinity"
    )


def msg_day5(first_name: str) -> str:
    return (
        f"Hey {first_name}! 👋\n\n"
        f"5 days in {config.COMMUNITY_NAME} — hope the daily updates have been useful. 🙌\n\n"
        f"Quick question: are you thinking about live trading?\n\n"
        f"If yes — here's what you should know:\n\n"
        f"✅ You can start with as little as $100 through AIMS FX, our recommended broker\n"
        f"✅ You don't need to figure it out alone — our team provides 1-on-1 education\n"
        f"✅ We walk you through everything: account setup, platform, your first trade\n"
        f"✅ No hidden fees. No pressure. Just real guidance from people who trade.\n\n"
        f"When you're ready, just reply to this message. "
        f"One of our team members will reach out personally and take it from there. 💼\n\n"
        f"No rush — we're here whenever you're ready.\n"
        f"— Elite by Infinity 🥇"
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
