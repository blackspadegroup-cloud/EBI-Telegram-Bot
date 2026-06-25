# EBI Bot Admin System — Framework, Workflow & Build Checklist

**Status:** Approved. Ready to build (Stage 1a next). This doc is the source of truth for
*how* it works and *where we are*. Update the checklist (§7) as work progresses.

---

## 1. Governance (your rules, encoded)

1. **One Admin: Steve.** Sole full control. No other admins.
2. **Everyone else is an Editor** — content only.
3. **Approval gate:** Editors can only *submit*. Nothing an Editor writes reaches the bot
   until **Steve approves** it.
4. **No code changes without Steve.** Branch protection on `main`; only Steve merges/deploys;
   Railway deploys only from `main`. Claude writes commit messages, **Steve pushes**.
5. **Secrets are Steve-only**, in Railway — never in the website or the DB.
6. **One system, one source of truth.** Supabase + this panel. **No Google Sheets.**

---

## 2. Roles & permissions

| Capability | Admin (Steve) | Editor (team) |
|---|---|---|
| Log into admin website | ✅ | ✅ |
| Write/edit content drafts (messages, FAQ, course) | ✅ | ✅ |
| **Submit** content for review | ✅ | ✅ |
| **Approve / reject** submitted content | ✅ | ❌ |
| Publish content live to the bot | ✅ (via approve) | ❌ |
| **View sent-message log** (Analytic + Community bots) | ✅ | ✅ (read-only) |
| **View / update client CRM** (notes, status, follow-up) | ✅ | ✅ (operational, no approval) |
| Change bot settings (times, toggles) | ✅ | ❌ |
| Edit intent rules / lead scoring | ✅ | ❌ |
| See secrets / tokens / keys | ❌ *(in Railway, not the app)* | ❌ |
| Change code / deploy | ✅ *(push to git)* | ❌ |

> **Note on the approval gate:** it applies to **content the bot sends to members**
> (messages, FAQ, course). It does **not** apply to internal CRM work — logging a client
> note or moving a lead's status is operational and happens live. Bot-facing = approval.
> Internal tracking = no approval.

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
        │   Team: CRM data entry      │
        └──────────────┬──────────────┘
                       │  reads/writes (anon key + RLS)
                       ▼
        ┌─────────────────────────────┐
        │   Supabase  (SOLE source     │
        │   of truth) — content        │
        │   versions, settings, CRM,   │
        │   approval queue, audit log  │
        └──────────────┬──────────────┘
                       │  reads ONLY approved content (cached, refreshes)
                       ▼
        ┌─────────────────────────────┐
        │   Telegram Bots (Railway)   │
        │   Community • Analytic • Edu│
        └─────────────────────────────┘
```

- The website talks **only to Supabase**. It never touches GitHub or Railway.
- **No Google Sheets** anywhere in the architecture. The panel is the only place client
  data is viewed or edited.
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
| `clients` | CRM: per-lead status, owner, notes, follow-up date | ❌ operational (no approval) |
| `audit_log` | Who changed/approved what, when | — |
| *(existing)* subscribers, messages, state, sent_news, qa, intent_events | unchanged | — |

> **Sent-message log** = a read-only view over the existing `telegram_messages` table (the
> bots already log every send as `out:{bot}:{type}`). No new table needed.
> **CRM** = the new `clients` table + views joining `telegram_subscribers`,
> `bot_intent_events`, `bot_qa_interactions`. Team enters notes/status manually in the panel.

---

## 6. Sequencing decision — Stage 1a BEFORE the Education Bot

**Build the content + approval pipeline first (Stage 1a), then the Education Bot.** The
Education Bot is just another *consumer* of the same pipeline — its 30 days are content rows
flowing through the same Editor-submit → Steve-approve workflow. Build the pipeline once and
the Education Bot inherits roles, approval, and versioning for free. Build the bot first and
we'd build the content plumbing twice. De-risk the plumbing once; reuse it everywhere.

---

## 7. Build checklist & progress tracker

Legend: ⬜ Not started · 🟡 In progress · ✅ Done · 🔴 Urgent

### Stage 0 — Foundations & governance
- ⬜ Enable branch protection on `main` (only Steve merges)
- ⬜ Confirm Railway deploys only from `main`
- ⬜ Confirm Steve is the only Railway/Supabase owner
- 🔴 **SECURITY: rotate the Supabase service-role key** — it's hardcoded in
  `EBI_Supabase_Sync.gs` and committed to GitHub. Coordinate with the bot's Railway key.
- ⬜ Remove `EBI_Supabase_Sync.gs` + `EBI_Bot_Sheets_Setup.gs` from the repo (Sheets retired)
- ✅ Approve this framework doc

### Stage 1a — Settings + Content pipeline + Approval (on existing bots)
- ✅ Create `bot_settings` table (seeded 9 defaults)
- ✅ Create `bot_content_versions` table (self-seeds from `i18n.py` STRINGS on first boot)
- ✅ Create `bot_audit_log` table
- ✅ Build DB-backed store (`services/store.py`) — cache + 60s refresh + safe fallback
- ✅ "Approved-only" read logic (verified: draft + older versions ignored, latest approved wins)
- ✅ `/reload` now also refreshes content + settings; `/pause` + `/resume` are DB-backed
- 🟡 Test live edit (edit a row in Supabase → see it in the bot) — after deploy
- 🟡 **Commit message provided to Steve → Steve pushes** (code is uncommitted)

### Stage 1b — Remaining content types
- ✅ `bot_faq_versions` + FAQ check runs before the AI (empty table = no-op; team adds entries)
- ✅ `bot_intent_rules` + `intent.py` reads DB rules with fallback (self-seeds from code on next deploy)
- ✅ `bot_edu_lessons` table created + 30 empty days seeded
- ✅ `/reload` reports content / settings / intent-rule / FAQ counts for quick verification

### Stage 2 — Admin website
**Stack (decided):** standalone client-side React app (Vite) + Supabase Auth + supabase-js.
Hosted free on Cloudflare Pages, served at **admin.elitesbyinfinity.com** (free subdomain).
Separate from the live marketing site so it can never affect it. Cost: $0.
- ✅ `bot_panel_users` roles table + `is_panel_admin()/is_panel_user()` helpers (Steve = sole admin)
- ✅ RLS policies on all `bot_` tables (panel users read; editors submit draft/pending; only admin approves)
- ✅ Scaffold app — static no-build `admin-panel/index.html` (supabase-js CDN) + email magic-link login
- ✅ Editor UI: content editor (draft → submit) — first slice
- ✅ Admin UI: approval queue (approve / reject)
- ✅ Day/night theme toggle
- ✅ Remaining UIs built: Settings, Intent rules, FAQ (submit→approve), CRM (pipeline + signals), Sent log, Education grid (30 days)
- ✅ Sticky + collapsible sidebar (icon-only collapse, persisted)
- ✅ Deployed to Cloudflare Pages + Email auth enabled + admin login verified
- ⬜ Markdown safety: input escaping done; deeper validation polish pending
- ⬜ Submit/approve notifications (Telegram DM to Steve)
- ⬜ Add team editor emails to `bot_panel_users` (when Steve is ready)
- ⬜ Go-live DNS: point `admin.elitesbyinfinity.com` (currently on the pages.dev URL)

### Stage 3 — EBI Education Bot (30-day course)
- ⬜ New bot via BotFather + token in Railway
- ⬜ Bot reads `bot_edu_lessons` (status='published' only)
- ⬜ **Gated daily drip:** one lesson/day at **09:00 GMT+8**; the user must tap
  "✅ I've learnt this" to confirm before the next day's lesson unlocks. Even after
  confirming, the next lesson only sends the following day. Progress tracked in
  `bot_edu_progress` (current_day = last sent, confirmed_day = last confirmed).
- ⬜ Team fills Day 1–30 via website → Steve approves → publishes

### Stage 4 — CRM (Phase 1 BUILT — see `EBI_CRM_Design.md` for full vision)
- ✅ CRM Phase 1 tables: `crm_leads`, `crm_pipeline_stages` (11 seeded), `crm_lead_history`, `crm_tasks`, `crm_activities` (RLS-enforced)
- ✅ Panel CRM rebuilt: **Pipeline** (11-stage drag-and-drop board), **Leads** (inbox + add + import Telegram signals), **lead profile** (fields, notes, tags, tasks, activity timeline), **Tasks** (due-sorted, complete)
- ✅ Verified live (insert/move/activity/cascade)
- ⬜ Phase 2 (gated on broker API): deposits/revenue, IB module, comms center, automation, support, marketing analytics — see design doc
- ⬜ Reminder to Steve: confirm AIMS FX / MetaApi API access before Phase 2

---

## 8. Bots in scope of the panel

All three bots are managed/visible through this system:
- **Community bot** — the bulk of editable content (welcome, onboarding, FAQ, intent, CTAs).
- **Analytic bot** — read-only **sent-message log** so editors can see what went out
  (admin-approved or auto-sent). Its *code behaviour* is already shipped: Gold/US-macro only
  (BTC removed); breaking-news digest 6×/day, AI picks 3, the management group picks 1,
  10-min auto-send. The panel adds visibility, not new behaviour.
- **Education bot** (future) — content-driven via `education_lessons` (Stage 3).

---

## 9. CRM — panel only (Google Sheets removed)

**Decision (Steve):** **No Google Sheets.** The panel is the single system for client
tracking. The team enters and updates client data **manually in the panel** from the start.

- Supabase `clients` is the single source of truth; the panel is the only read/write surface.
- The existing Apps Script sync (`EBI_Supabase_Sync.gs`) and Sheet-setup script
  (`EBI_Bot_Sheets_Setup.gs`) are **retired** — remove them from the repo (Stage 0).
- This eliminates the two-editable-systems risk (drift, conflicts, lost edits) entirely.

**Security follow-up:** retiring the sync also removes the file that leaked the Supabase
service-role key — but the key is still in git history, so **rotate it anyway** (Stage 0).

---

## 10. Already shipped (live in the bots today)
- Analytic bot = Gold/US-macro only (BTC removed)
- Breaking-news digest: 6×/day, AI picks 3, management group picks 1, 10-min auto-send
