# EBI Trading CRM — World-Class Design Blueprint

**Author's framing (read first).** This designs a Salesforce/HubSpot/GoHighLevel-class CRM
*tailored for a forex/gold trading business* — but engineered to be shipped by a small team,
on top of what EBI already has, not as a 12-month from-scratch megaproject.

Two strategic truths shape every decision below:

- **You already own ~40% of the data model.** Supabase already has `members` (with
  `sponsor_id` = the IB tree), `commissions`, `commission_levels`, `subscriptions`,
  `mt_accounts`, `mt_signals`, `academy_progress`, plus all Telegram lead data
  (`telegram_subscribers`, `bot_intent_events`, `bot_qa_interactions`). We extend this,
  we don't replace it.
- **The money modules depend on broker data you don't yet control.** Deposits, withdrawals,
  trading volume, funded-account status and KYC live in your broker (AIMS FX) / MetaApi.
  Until those feed in, those dashboards are estimates. The design treats broker integration
  as a first-class dependency, not an afterthought.

---

## 1. Full feature list (by module)

| # | Module | Core features | Data today | Gap to fill |
|---|--------|---------------|------------|-------------|
| 1 | **Lead Management** | Multi-source capture (web form, Meta, TikTok, IG, Telegram, WhatsApp, referral, webinar, manual); source/campaign tracking; lead scoring; qualification status; interaction history; owner assignment; follow-up reminders; duplicate detection | `bot_intent_events`, `telegram_subscribers` | `leads`, `lead_sources`, `campaigns` tables; web/Meta webhooks |
| 2 | **Sales Pipeline** | 11 stages, drag-and-drop, per-stage automation, aging/rotting indicators | partial (`bot_clients.stage`) | `pipeline_stages`, stage history |
| 3 | **Client Profile** | Personal/contact, country, language, experience, risk profile, preferred market, broker accounts, deposits/withdrawals, volume, account manager, documents, notes, tags, full timeline | `members`, `mt_accounts`, `subscriptions` | `client_profiles`, `documents`, `tags`, `activities` |
| 4 | **Communication Center** | Email, WhatsApp, Telegram, calls, meeting notes, broadcasts — all auto-logged to the timeline | `telegram_messages` | `communications`, channel integrations |
| 5 | **Task Management** | Reminders, call/meeting scheduling, to-do lists, assignment, priority, due dates, completion | — | `tasks` |
| 6 | **IB & Referral** | Parent/child tree, referral source, downline count, deposits generated, volume, commission eligibility, leaderboard, commission history, status | `members.sponsor_id`, `commissions`, `commission_levels` | reporting views, downline rollups |
| 7 | **Deposit & Revenue** | Total/monthly deposits, new funded accounts, active traders, avg deposit, revenue by campaign/IB/salesperson, conversion | `subscriptions` | `transactions` (broker feed), attribution |
| 8 | **Marketing Analytics** | CPL, CPA, campaign ROI, source performance, funnel conversion | — | `campaigns`, ad-spend ingestion |
| 9 | **Automation Engine** | Event triggers + actions (welcome, assign, follow-up SLA, onboarding, IB milestones, dormancy flag, reactivation) | bot logic | `automations`, `automation_runs` |
| 10 | **Customer Support** | Tickets, categories, priorities, assignment, SLA timers, resolution, internal comments, CSAT | — | `tickets`, `ticket_messages` |
| 11 | **Reporting** | KPI dashboards, drill-down, charts: leads, conversion, deposits, active clients, sales-by-rep, IB perf, campaign perf, MoM growth, churn, reactivation | scattered | materialized reporting views |

---

## 2. Roles & permissions

| Capability | Super Admin | Sales Mgr | Sales Exec | Support | Marketing | IB Mgr | Finance | Client Portal |
|---|---|---|---|---|---|---|---|---|
| All settings / users / audit | ✅ | — | — | — | — | — | — |
| View all leads/clients | ✅ | ✅ (team) | own + assigned | assigned | — | IB-linked | own only |
| Edit pipeline / assign | ✅ | ✅ | own | — | — | — | — |
| Communications | ✅ | ✅ | ✅ | ✅ | broadcast | ✅ | — |
| Tickets | ✅ | view | view | ✅ | — | — | raise own |
| IB tree & commissions | ✅ | view | — | — | — | ✅ | own downline |
| Deposits / revenue | ✅ | team totals | own | — | campaign rev | IB rev | ✅ |
| Marketing analytics | ✅ | view | — | — | ✅ | — | — |
| Reports | ✅ | team | own | support KPIs | mktg KPIs | IB KPIs | — |

Enforced at the database layer with Row-Level Security (same pattern already live on the
`bot_*` tables), driven by a `crm_users(email, role, team_id)` table. Security never relies
on the UI alone.

---

## 3. Database schema

**Reuse (existing):** `members`, `subscriptions`, `commissions`, `commission_levels`,
`mt_accounts`, `mt_signals`, `mt_positions`, `academy_progress`, `telegram_subscribers`,
`telegram_messages`, `bot_intent_events`, `bot_qa_interactions`.

**New CRM tables (`crm_` namespace, RLS-enforced):**

```
crm_users(id, email, role, team_id, display_name, active)
crm_teams(id, name, manager_id)

leads(id, full_name, email, phone, country, language, source_id, campaign_id,
      score, status, qualification, owner_id, member_id?, dedupe_hash,
      created_at, last_activity_at)            -- member_id links once converted
lead_sources(id, name, channel)                -- web/meta/tiktok/ig/telegram/whatsapp/referral/webinar/manual
campaigns(id, name, channel, spend, utm, start, end)

pipeline_stages(id, key, label, order, is_terminal)   -- New Lead … Active Trader … Lost
pipeline_history(id, subject_type, subject_id, from_stage, to_stage, by, at)

client_profiles(member_id PK→members, risk_profile, experience, preferred_market,
                account_manager_id, kyc_status, tags[])
documents(id, member_id, type, url, status, uploaded_by, at)   -- KYC etc.
transactions(id, member_id, mt_account_id?, type[deposit|withdrawal], amount, ccy,
             source[broker|stripe|manual], external_id, status, at)   -- broker feed
activities(id, subject_type, subject_id, type, summary, actor_id, at)  -- universal timeline
tags(id, name, color)   tag_links(tag_id, subject_type, subject_id)

communications(id, subject_type, subject_id, channel, direction, body, actor_id,
               external_id, at)
tasks(id, title, type, priority, due_at, assignee_id, subject_type, subject_id,
      status, completed_at)

ib_links(member_id, parent_id, tier)           -- derived/denormalised from members.sponsor_id
ib_stats_daily(member_id, date, downline, deposits, volume, commission)  -- rollup

tickets(id, member_id, category, priority, subject, status, assignee_id,
        sla_due_at, csat, created_at, resolved_at)
ticket_messages(id, ticket_id, author_id, body, internal, at)

automations(id, name, trigger, conditions_json, actions_json, active)
automation_runs(id, automation_id, subject_id, status, at)
crm_audit_log(id, actor, action, entity, entity_id, detail, at)
notifications(id, user_id, kind, payload, read, at)
```

**Key relationships:** `leads.member_id → members.id` (on conversion);
`members.sponsor_id → members.id` (IB tree); `transactions.member_id → members.id`;
`commissions.earner_id/source_id → members.id`; everything timelined through `activities`
via polymorphic `(subject_type, subject_id)`.

---

## 4. Navigation structure

```
EBI CRM
├── Dashboard            (role-aware KPIs + my tasks + alerts)
├── Leads                (inbox, scoring, dedupe, assign)
├── Pipeline             (drag-and-drop board, 11 stages)
├── Clients              (list + rich profile + timeline)
├── Communications       (unified inbox: email/WA/TG/calls)
├── Tasks                (my day, team board, calendar)
├── IB / Referrals       (tree, leaderboard, commissions)
├── Finance              (deposits, withdrawals, revenue)
├── Marketing            (campaigns, sources, funnel, ROI)
├── Support              (ticket queue, SLA, CSAT)
├── Reports              (KPI library + drill-down)
├── Automations          (visual rules builder)
└── Settings             (users, roles, pipelines, tags, integrations, audit)
```

---

## 5. User-flow diagrams (text)

**Lead → Active Trader**
```
Capture (form/ad/TG/WA) → dedupe check → auto-score → assign owner
  → [New Lead] → Contacted → Interested → Follow-up
  → KYC Pending (docs uploaded, verified)
  → Account Opened (broker acct linked via mt_accounts)
  → First Deposit (transactions: type=deposit)  ──▶ onboarding automation
  → Active Trader (volume threshold)  ──▶ retention cadence
  → (Dormant 30d no activity) ──▶ reactivation campaign ──▶ Reactivated / Lost
```

**Support ticket SLA**
```
Client raises ticket → category+priority → auto-assign by category
  → SLA timer starts → agent replies (timer pause) → resolved → CSAT survey
  → breach? escalate to Support lead + notify
```

**IB commission**
```
Referred client deposits → transaction posts → attribute to sponsor chain (tiers)
  → commission rows generated per commission_levels → IB Mgr approves
  → payable shown on IB leaderboard + commission history
```

---

## 6. Dashboard wireframes (text)

**Management dashboard**
```
┌───────────────────────────────────────────────────────────────┐
│ KPIs:  Leads(▲)   Conv%   Deposits$   Active   Churn%   IB rev  │
├──────────────────────────────┬────────────────────────────────┤
│ Pipeline funnel (bars)        │ Revenue trend (line, MoM)       │
├──────────────────────────────┼────────────────────────────────┤
│ Leads by source (donut)       │ Sales-by-rep leaderboard (bars) │
├──────────────────────────────┴────────────────────────────────┤
│ Live activity feed  ·  My tasks due  ·  SLA breaches            │
└───────────────────────────────────────────────────────────────┘
```

**Pipeline board** — Kanban columns = the 11 stages, draggable cards showing name, country
flag, score chip, owner avatar, $ potential, days-in-stage (turns amber→red when rotting).

**Client profile** — left: identity + KYC + tags; centre: tabbed timeline (all activity,
comms, tasks, deposits, trades); right: quick actions (log call, add task, move stage,
message). Financial-terminal density, dark by default.

---

## 7. Page-by-page breakdown (condensed)

- **Dashboard** — role-aware KPI tiles, charts, my-tasks, alerts.
- **Leads** — sortable/filterable inbox; bulk assign; score + source columns; dedupe banner; quick-convert.
- **Pipeline** — Kanban; drag updates `pipeline_history`; per-stage automation hooks; rotting alerts.
- **Client profile** — 360° view; timeline from `activities`; deposits from `transactions`; trades from `mt_*`; documents/KYC; tags; notes.
- **Communications** — unified threaded inbox per channel; templates; broadcast composer; auto-log.
- **Tasks** — "my day," team board, calendar sync; priority + due; completion tracking.
- **IB/Referrals** — interactive downline tree; leaderboard; commission ledger + payout status.
- **Finance** — deposits/withdrawals ledger; revenue by campaign/IB/rep; funded-accounts; export.
- **Marketing** — campaign table with spend→CPL→CPA→ROI; source performance; funnel.
- **Support** — ticket queue with SLA countdown; detail with internal/public replies; CSAT.
- **Reports** — KPI library, saved views, drill-down, CSV/PDF export.
- **Automations** — trigger→condition→action visual builder; run log.
- **Settings** — users/roles, pipelines, tags, channel integrations, 2FA, audit log.

---

## 8. Suggested tech stack

- **Frontend:** React + TypeScript + Vite, TanStack Query/Table, Tailwind, Recharts;
  drag-and-drop via dnd-kit. Dark-first, terminal-density design system.
- **Backend / data:** **Supabase** (Postgres + RLS + Auth + Realtime + Storage + Edge
  Functions) — you already run it; reuse it. Edge Functions for webhooks, broker sync, automations.
- **Auth & security:** Supabase Auth + RLS + 2FA (TOTP); secrets in env, never client.
- **Integrations layer:** Edge Functions + a lightweight queue (pg_cron + a `jobs` table)
  for broker/WhatsApp/email sync; Zapier/webhooks for the long tail.
- **Hosting:** Cloudflare Pages (frontend, free) + Supabase (managed). Same footprint as today.
- **Why not a new platform:** building on Supabase keeps leads, members, commissions and
  trading data in *one* database — the single biggest advantage you have over bolting on HubSpot.

---

## 9. API architecture

- **Data access:** Supabase auto-generated REST/GraphQL + Realtime, gated by RLS (no bespoke CRUD API to maintain).
- **Edge Functions (serverless) for the verbs RLS can't express:**
  - `ingest/lead` — public webhook for web form / Meta / TikTok / WhatsApp / Telegram → dedupe → score → assign.
  - `broker/sync` — pull deposits/withdrawals/volume/account status from broker/MetaApi → `transactions`, `mt_accounts`.
  - `automation/run` — evaluate triggers, execute actions, log to `automation_runs`.
  - `comms/send` — outbound email/WhatsApp/Telegram via providers; log to `communications`.
  - `commissions/calc` — attribute deposits up the sponsor chain.
- **Webhooks in:** Meta/TikTok lead ads, Stripe, WhatsApp Business, Telegram, broker callbacks.
- **Webhooks out / Zapier:** generic event bus so non-devs wire new tools without code.
- **Contracts:** versioned (`/v1/...`), idempotency keys on ingest, signed webhook secrets.

---

## 10. Automation workflows (starter set)

| Trigger | Condition | Action |
|---|---|---|
| New lead created | any | Notify assigned rep; start 24h follow-up timer |
| 24h no follow-up | status=New/Contacted | Escalate to Sales Mgr; mark "rotting" |
| Lead → KYC Pending | docs missing | DM/email checklist; create task |
| First deposit posts | transaction=deposit | Move to First Deposit; trigger onboarding sequence; thank-you |
| IB downline deposit | milestone reached | Alert IB Mgr; update leaderboard |
| No activity 30d | status=Active | Flag Dormant; enqueue reactivation campaign |
| Ticket SLA 80% elapsed | unresolved | Warn agent; at breach escalate |
| Reactivation reply | dormant client responds | Reassign to rep; create call task |

---

## 11. Search, filters, notifications, security, integrations

- **Filters (everywhere):** country, language, salesperson, campaign, source, deposit amount, last activity, status, tags, date range — saved as reusable views.
- **Notifications:** in-app (Realtime), browser push, email, Telegram DM (you already have the bot), daily digest.
- **Security:** RLS role permissions, full `crm_audit_log`, 2FA, encryption at rest (Supabase), encrypted document storage, scheduled backups, least-privilege keys.
- **Future integrations (architected for):** broker APIs/MetaApi, Stripe, Telegram, WhatsApp Business, email (Resend/SES), Google Calendar, Zapier, generic webhooks, AI assistants (lead summarisation, next-best-action, churn prediction).

---

## 12. Roadmap

**Phase 1 — MVP (weeks, not months). Ship the sales core on data you already have.**
- `leads` + sources/campaigns + capture webhook (web form + Telegram + manual).
- Pipeline board (11 stages) with drag-and-drop + history.
- Client profile reading existing `members`/`mt_accounts`/`subscriptions` + notes/tags/timeline.
- Tasks + follow-up reminders. Roles (Super Admin, Sales Mgr, Sales Exec) + RLS.
- Basic dashboard (leads, conversion, my tasks). This already extends the panel you have.

**Phase 2 — Growth. Add the money + retention engine.**
- Broker/MetaApi sync → `transactions`, funded accounts, volume → Finance & Revenue dashboards.
- IB/referral module on `members.sponsor_id` + `commissions` (tree, leaderboard, payouts).
- Communication Center (email + WhatsApp + Telegram unified) + broadcasts.
- Automation engine + marketing analytics (CPL/CPA/ROI). Support tickets + SLA.

**Phase 3 — Enterprise.**
- Client portal, advanced reporting/BI, AI (churn prediction, next-best-action, auto-summaries),
  multi-brand/multi-broker, granular role matrix, Zapier marketplace, mobile app, SOC2-style controls.

---

## 13. Recommendations to compete with the big SaaS players

1. **Win on unification, not feature count.** HubSpot can't see a client's *trades*. You can —
   leads, deposits, IB tree and trading activity in one database is your moat. Lead with the 360° trader profile.
2. **Trading-native pipeline & vocabulary.** KYC, First Deposit, Funded, Active Trader, Dormant —
   generic CRMs force you to bend; yours speaks forex natively.
3. **Ruthless "minimal clicks."** A rep should log a call, set a follow-up, and move a stage in
   ≤3 clicks. Speed beats features for daily adoption.
4. **Automation as the retention weapon.** Dormancy flags + reactivation campaigns recover revenue
   competitors leave on the table.
5. **IB leaderboard = growth flywheel.** Gamified, transparent commissions make IBs sell for you.
6. **Don't build what you can rent (yet).** Email/WhatsApp sending, calendar, payments — integrate,
   don't rebuild. Spend your engineering on the trading-specific 20% nobody else has.
7. **Phase honestly.** Resist building Phase 3 modules with Phase 1 data. Empty dashboards kill trust faster than missing features.

---

## 14. Honest dependency & risk register

- **Broker data access is the critical path.** Confirm what AIMS FX / MetaApi exposes (deposits,
  volume, account status, webhooks) *before* committing to Finance/IB-accuracy features.
- **PDPA / data protection:** storing KYC documents and personal data carries legal duties — plan consent, retention and access controls in Phase 1, not later.
- **Adoption risk:** a CRM nobody updates is worthless. Phase 1 must be faster than the WhatsApp-and-memory workflow it replaces, or the team won't switch.
- **Scope discipline:** this document is the 100% vision; Phase 1 is ~15% of it and delivers most of the daily value. Build that first.
