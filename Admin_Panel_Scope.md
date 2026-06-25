# EBI Bot Admin Panel — Stage 1 Scope

**Goal:** a login-protected website where non-technical admins/team can edit the bot's
content and behaviour, without code or redeploys. The page reads/writes **Supabase**.
**GitHub and Railway are never touched by the website** — GitHub holds code, Railway runs
the bot, Supabase holds settings. A bad setting can't break the deploy.

---

## 1. What moves to the DB (admin-editable in the website)

Everything here is currently hardcoded in Python and would become Supabase rows.

| Area | Today (in code) | Becomes DB table | Who edits |
|---|---|---|---|
| **Toggles & timings** | `config.py`, `market_bot.py` schedule | `bot_settings` | Admin |
| **Bot content / messages** | `services/i18n.py` `STRINGS` | `bot_content` | Admin + Editor |
| **FAQ (canned answers)** | *(none yet — AI-only)* | `faq` | Admin + Editor |
| **Intent levels for clients** | `services/intent.py` `INTENT_RULES` | `intent_rules` | Admin |
| **Education course (future bot)** | *(doesn't exist yet)* | `education_lessons` | Editor fills, Admin publishes |

### 1a. `bot_settings` — toggles & timings (no code, takes effect on next refresh)
- Pause / resume each bot
- Market update times (currently 07:00 / 14:00 / 19:00)
- Breaking-news slots (currently 08/11/14/17/20/23) + number of options (3) + auto-send timeout (10 min)
- Weekend mindset time
- `COMMUNITY_NAME`, `BOOKING_URL`
- News lookback hours
- ⚠️ Time/schedule changes need the bot to **re-read and reschedule** (see §4).

### 1b. `bot_content` — every message the bot sends
Replaces the `STRINGS` dictionary. One row per (key, language):
- `welcome_dm`, `about_ebi`, `how_it_works`, `lead_magnet` (starter guide), `book_call`,
  `ask_hint`, `capture_thanks`, `declined_topic`, menu button labels
- `onboarding_day1`, `onboarding_day3`, `onboarding_day5`
- `soft_cta_high`, `soft_cta_medium`, `milestone_dm`, `reengagement_dm`, `start_trading_text`
- Both **English + Simplified Chinese** per key.
- **This is goal #2's "change the welcome message" — and far more.**

### 1c. `faq` — canned Q&A the bot checks before calling the AI
New capability (today every answer is AI-generated). Each row:
- `question` (or trigger keywords), `answer_en`, `answer_zh`, `tags`, `active`
- **This is goal #2's "add or minus the FAQ."**

### 1d. `intent_rules` — lead-scoring levels
Replaces `INTENT_RULES`. Each row:
- `keywords` (list), `label` (e.g. "Account Opening"), `points` (1–3),
  `send_alert` (true = ping the Potential Client group), `active`
- **This is goal #2's "level of intent for client."**

### 1e. `education_lessons` — the EBI Education Bot (goal #4)
Pre-create the framework Day 1 → Day 30; the team fills content:
- `day_number` (1–30), `title_en/zh`, `body_en/zh`, `media_url` (optional video/image),
  `status` (`draft` / `published`), `updated_by`, `updated_at`
- Admin seeds 30 empty rows; **Editors fill them in**; Admin flips `published`.

---

## 2. What stays a SECRET (Railway Variables only — NEVER in the DB or the website)

These must never appear in a browser-facing app. Exposing a token = someone can hijack the bot.

| Secret | Why it stays out |
|---|---|
| `MARKET_BOT_TOKEN`, `COMMUNITY_BOT_TOKEN` | Full control of the bots. |
| `GROQ_API_KEY` | Your AI billing/quota. |
| `NEWS_API_KEY` | Third-party quota. |
| `SUPABASE_KEY` (service role) | Full DB access. The website uses a **separate anon key + RLS**, not this. |

## 3. Grey zone — Railway config, keep out of the public UI for v1

Not secret, but sensitive plumbing that rarely changes and can misroute everything if wrong.
Keep in Railway Variables for now; expose later only with strong validation:
- `ADMIN_IDS`, `MARKET_GROUP_ID`, `COMMUNITY_GROUP_ID`, `MANAGEMENT_GROUP_ID`,
  `POTENTIAL_CLIENT_GROUP_ID`, `APPROVAL_GROUP_ID`, `TIMEZONE`

---

## 4. Implementation notes (the parts that bite if ignored)

1. **The bot must re-read the DB.** Today values load once at startup. Add a settings/content
   cache with a short refresh (e.g. 60s) or a `/reload` admin command. Schedule changes
   specifically need APScheduler jobs to be rebuilt on reload — more than a simple toggle.
2. **Markdown safety.** The bot sends Telegram Markdown. A stray `*` or `_` typed by a
   non-coder can break message rendering or fail the send. The website must validate/escape
   content on save, or the bot must send defensively.
3. **Two roles (needed for goal #4).** `Admin` = everything. `Editor` = content only
   (FAQ, messages, education lessons) — cannot see secrets, change settings, or broadcast.
   Supabase Auth + Row-Level Security handles this cleanly.
4. **Fallback.** If the DB is unreachable, the bot should fall back to safe built-in defaults,
   not crash. (Some functions already degrade gracefully; this must be deliberate.)

---

## 5. Suggested build order

- **Stage 1a (proves the wiring, ~low effort):** create `bot_settings` + `bot_content`,
  refactor the bot to read them with a cache, seed from current values. Use the **Supabase
  table editor** as the temporary admin UI. No website yet.
- **Stage 1b:** add `faq`, `intent_rules`, `education_lessons`.
- **Stage 2 (the website):** Next.js page on `admin.ebidomain.com` (Vercel or Railway),
  Supabase Auth login, Admin/Editor roles, friendly forms (toggles, time pickers, a Day 1–30
  grid for the course). Branded, no SQL for the team.

> Recommendation: do **1a first**. It de-risks everything — if the bot can't reliably read
> settings from Supabase with a clean fallback, a pretty website on top is worthless.
