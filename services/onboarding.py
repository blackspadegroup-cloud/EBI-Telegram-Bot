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
from services.i18n import t, get_lang
from utils.logger import get_logger

log = get_logger("onboarding")


# ── Message templates (bilingual via i18n) ────────────────────────────────────

def msg_day1(first_name: str, lang: str = "en") -> str:
    return t("onboarding_day1", lang, name=first_name)


def msg_day3(first_name: str, lang: str = "en") -> str:
    return t("onboarding_day3", lang, name=first_name)


def msg_day5(first_name: str, lang: str = "en") -> str:
    return t("onboarding_day5", lang, name=first_name)


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
        lang = get_lang(chat_id)
        try:
            from telegram.constants import ParseMode
            await bot.send_message(
                chat_id=chat_id,
                text=message_fn(first_name, lang),
                parse_mode=ParseMode.MARKDOWN,
            )
            set_onboarding_step(chat_id, step)
            log.info(f"Sent onboarding step {step} to {first_name} ({chat_id})")
        except Exception as e:
            log.warning(f"Could not send onboarding step {step} to {chat_id}: {e}")
