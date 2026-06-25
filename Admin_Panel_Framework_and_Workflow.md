# EBI Bot Admin System — Framework, Workflow & Build Checklist

**Status:** Planning. Nothing built yet. This doc is the source of truth for *how* it works
and *where we are*. Update the checklist (§7) as work progresses.

---

## 1. Governance (your rules, encoded)

1. **One Admin: Steve.** Sole full control. No other admins.
2. **Everyone else is an Editor** — content only.
3. **Approval gate:** Editors can only *submit*. Nothing an Editor writes reaches the bot until
   **Steve approves** it.
4. **No code changes without Steve.** Branch protection on `main`; only Steve merges/deploys;
   Railway deploys only from `main`. Claude writes commit messages, **Steve pushes**.
5. **Secrets are Steve-only**, in Railway — never in the website or the DB.

---

## 2. Roles & permissions

| Capability | Admin (Steve) | Editor (team) |
|---|---|---|
| Log into admin website | ✅ | ✅ |
| Write/edit content drafts (messages, FAQ, course) | ✅ | ✅ |
| **Submit** content for review | ✅ | ✅ |
| **Approve / reject** submitted content | ✅ | ❌ |
| Publish content live to the bot | ✅ (via approve) | ❌ |
| Change bot settings (times, toggles) | ✅ | ❌ |
| Edit intent rules / lead scoring | ✅ | ❌ |
| See secrets / tokens / keys | ❌ *(in Railway, not the app)* | ❌ |
| Change code / deploy | ✅ *(push to git)* | ❌ |

> Editors never have a "go live" button. The only path to the bot is **through Steve**.

---

## 3. Content lifecycle (the approval workflow)

Every Editor-editable item (a message, an FAQ entry, a course day) moves through these states:

```
[ Draft ] --submit--> [ Pending Review ] --approve--> [ Approved / LIVE ]
   ^                          |
   |                          +--reject (with note)--> back to [ Draft ]
   |
   +-- Editor keeps editing until happy
```

Rules that make this safe:
- **The bot reads ONLY the latest `approved` version of each item.** Drafts and pending
  submissions never affect the live bot.
- **Versioned, not overwritten.** Approving creates a new live version; the previous one is
  kept → full audit trail + one-click rollback.
- **Notify on submit.** When an Editor submits, Steve gets pinged (Telegram DM and/or email).
- **Notify on decision.** Editor sees approved/rejected + Steve's note.
- **Settings & intent rules skip the queue** — only Steve can touch them, so there's nothing
  to approve; his change applies on the next bot refresh.

---

## 4. System architecture

```
        ┌─────────────────────────────┐
        │   Admin Website             │
        │   (Next.js, Supabase Auth)  │
        │   Editors: draft + submit   │
        │   Steve: approve / settings │
        └──────────────┬──────────────┘
                       │  reads/writes (anon key + RLS)
                       ▼
        ┌─────────────────────────────┐
        │   Supabase  (source of truth)│
        │   content versions, settings,│
        │   approval queue, audit log  │
        └──────────────┬──────────────┘
                       │  reads ONLY approved content (cached, refreshes)
                       ▼
        ┌─────────────────────────────┐
        │   Telegram Bots (Railway)   │
        │   Market • Community • Edu  │
        └─────────────────────────────┘
```

- The website talks **only to Supabase**. It never touches GitHub or Railway.
- Secrets live in **Railway Variables**; the website uses a restricted Supabase anon key + RLS.

---

## 5. Data model (high level)

| Table | Purpose | Approval? |
|---|---|---|
| `bot_content_versions` | Every message string (key, lang, value, status, author, reviewer, note, timestamps) | ✅ Editor → Steve |
| `faq_versions` | FAQ Q&A entries, versioned | ✅ Editor → Steve |
| `education_lessons` | Day 1–30 course content, versioned | ✅ Editor → Steve |
| `bot_settings` | Toggles & timings | ❌ Admin-only |
| `intent_rules` | Lead-scoring keywords & levels | ❌ Admin-only |
| `audit_log` | Who changed/approved what, when | — |
| *(existing)* subscribers, messages, state, sent_news, qa, intent_events | unchanged | — |

---

## 6. Sequencing decision — Stage 1a BEFORE the Education Bot

**Recommendation: build the content + approval pipeline first (Stage 1a), then the Education Bot.**

Why: the Education Bot is just another *consumer* of the same content + approval pipeline —
its 30 days are content rows that flow through the exact same Editor-submit → Steve-approve
workflow. If we build the pipeline first, the Education Bot inherits roles, approval, and
versioning for free. Build the bot first and we'd build the content plumbing twice and bolt
governance on afterwards (fragile). De-risk the plumbing once; reuse it everywhere.

---

## 7. Build checklist & progress tracker

Legend: ⬜ Not started · 🟡 In progress · ✅ Done

### Stage 0 — Foundations & governance
- ⬜ Enable branch protection on `main` (only Steve merges)
- ⬜ Confirm Railway deploys only from `main`
- ⬜ Confirm Steve is the only Railway/Supabase owner
- ⬜ Approve this framework doc

### Stage 1a — Settings + Content pipeline + Approval (on existing bots)
- ⬜ Create `bot_settings` table + seed from current code values
- ⬜ Create `bot_content_versions` table + seed from `i18n.py` STRINGS
- ⬜ Create `audit_log` table
- ⬜ Refactor bot to read settings + content from Supabase (cache + 60s refresh + safe fallback)
- ⬜ Implement "approved-only" read logic (bot ignores draft/pending)
- ⬜ Add `/reload` admin command (force refresh)
- ⬜ Test: edit a row in Supabase → see it live in the bot
- ⬜ **Commit message provided to Steve → Steve pushes**

### Stage 1b — Remaining content types
- ⬜ Create `faq_versions` table + bot checks FAQ before AI
- ⬜ Create `intent_rules` table + refactor `intent.py` to read it
- ⬜ Create `education_lessons` table (seed 30 empty days)

### Stage 2 — Admin website
- ⬜ Scaffold Next.js app + Supabase Auth (email login)
- ⬜ Roles: Admin (Steve) vs Editor + Row-Level Security
- ⬜ Editor UI: draft + submit (messages, FAQ, course)
- ⬜ Admin UI: approval queue (approve / reject + note)
- ⬜ Admin UI: settings (toggles, time pickers), intent rules
- ⬜ Markdown safety: validate/escape content on save
- ⬜ Submit/approve notifications (Telegram DM to Steve)
- ⬜ Deploy to `admin.<yourdomain>` (Vercel/Railway)

### Stage 3 — EBI Education Bot (30-day course)
- ⬜ New bot via BotFather + token in Railway
- ⬜ Bot reads `education_lessons` (approved + published only)
- ⬜ Daily drip / on-demand "Day N" delivery, bilingual
- ⬜ Team fills Day 1–30 via website → Steve approves → publishes

---

## 8. What's NOT in this project (already shipped separately)
- Analytic bot = Gold/US-macro only (BTC removed)
- Breaking-news digest: 6×/day, AI picks 3, Steve's group picks 1, 10-min auto-send
