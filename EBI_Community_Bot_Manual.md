# EBI Community Bot — Management Manual
**Elite by Infinity | Living Document | Last updated: June 2026**

---

## What This Bot Does (Overview)

The EBI Community Bot is an AI-powered assistant that runs 24/7 inside your Telegram community group. It serves three purposes:

1. **Welcomes and nurtures new members** — automatically, without any admin effort
2. **Answers trading questions** — so admins don't need to reply to every question
3. **Identifies and alerts you to potential clients** — people showing real intent to open a trading account

Think of it as a junior team member that never sleeps, never misses a new member, and flags every hot lead to you the moment they appear.

---

## Bot Groups at a Glance

| Group | Purpose |
|---|---|
| Community Group | Main group where members interact and the bot responds |
| EBI Bot Management | Where the bot sends weekly content for admin approval before posting |
| EBI Potential Client Update | Where the bot sends intent alerts about high-value leads |

---

## Part 1 — Automated Features (No Admin Action Needed)

These run automatically every day. You don't need to do anything.

---

### 1.1 Welcome New Members

**When:** Every time someone joins the community group
**What happens:**
- The bot posts a warm welcome message in the group, mentioning the new member by name
- Within seconds, it sends a private DM to the new member introducing itself and listing what it can help with
- The member is saved to your database automatically

**What the DM says:**
> Hi [Name]! Welcome to Elite by Infinity. I'm your AI assistant. I can help you with Gold (XAUUSD), Bitcoin, trading basics, risk management, economic news, and community info. Just send me a message anytime!

**Note:** If a member has Telegram privacy settings that block DMs, the bot logs this quietly and moves on. The public welcome still posts.

---

### 1.2 DM Onboarding Sequence

**When:** Automatically on Day 1, Day 3, and Day 5 after joining (sent at 9:00 AM SGT)
**Purpose:** Build trust and educate new members before asking them to do anything

| Day | Message Topic |
|---|---|
| Day 0 | Welcome DM (sent immediately on join) |
| Day 1 | "Gold Trading in 60 Seconds" — explains the 3 forces that move Gold |
| Day 3 | "The #1 Mistake New Traders Make" — stop loss education + risk rule |
| Day 5 | "Ready to Take the Next Step?" — soft conversion CTA, intro to live trading |

**Key principle:** No hard selling. By Day 5, the member has received 3 educational messages and trusts EBI as a source of real value. The Day 5 message simply opens a door.

---

### 1.3 AI Question & Answer

**When:** Any time a member mentions the bot in the group (@BotName) or replies to one of its messages, or sends it a private DM
**What it does:** Answers trading questions in simple, friendly language. Responds in the same language the member used.

**Topics it handles:**
- Gold (XAUUSD) questions
- Bitcoin and crypto basics
- Trading terminology (pips, lots, leverage, margin, etc.)
- Risk management concepts
- Economic indicators (CPI, FOMC, NFP, etc.)
- Basic technical analysis
- Community rules and FAQs
- How to get started with trading

**Topics it declines (by design):**
- "Should I buy now / sell now?"
- "Will Gold go up?"
- "What's your price target?"
- Anything asking for specific signals or guaranteed profit

When someone asks a declined question, the bot politely explains it can only educate, not advise — and redirects them.

**Rate limiting:** In the group, each member can ask up to 10 questions per hour. In private DMs, there is no limit.

---

### 1.4 Intent Detection & Lead Alerts

**When:** Every time a member asks a question (group or DM)
**What it does:** The bot silently scans each message for signs that the member is thinking about opening a trading account. When it detects one, it:

1. Records the signal in the database
2. Sends an instant alert to the **EBI Potential Client Update** group

**Intent categories and what triggers them:**

| Signal | Examples | Score |
|---|---|---|
| Account Opening 🔴 | "how do I open an account", "how do I get started" | 3 pts |
| Broker Selection 🔴 | "which broker do you recommend", "is this broker safe" | 3 pts |
| Deposit Amount 🔴 | "how much do I need to start", "minimum deposit" | 3 pts |
| Platform Inquiry 🔴 | "MT4 vs MT5", "which trading app", "MetaTrader" | 3 pts |
| Trading Costs 🔴 | "what are the spreads", "commission", "swap fees" | 3 pts |
| Funding Methods 🔴 | "how do I deposit", "can I use bank transfer", "USDT deposit" | 3 pts |
| Demo Account 🟡 | "is there a demo account", "practice trading" | 2 pts |
| How to Trade 🟡 | "how do I trade Gold", "where do I trade" | 2 pts |
| Risk Management 🟡 | "stop loss", "take profit", "position size" | 2 pts |
| Beginner Education 🟢 | "what is a pip", "what is forex", "what is Bitcoin" | 1 pt |

**What the alert looks like in EBI Potential Client Update:**
```
🎯 Potential Client Signal
━━━━━━━━━━━━━━━━━━━━━━
👤 @john_trader
🏷️ Intent: Account Opening
📊 Cumulative Score: 5 pts
━━━━━━━━━━━━━━━━━━━━━━
💬 Their question:
"How do I open a trading account for Gold?"
━━━━━━━━━━━━━━━━━━━━━━
💡 Follow up now while interest is hot.
```

**Action for admins:** When you see an alert, reach out to that member personally. The faster you follow up, the higher the conversion rate.

---

### 1.5 Soft Call-to-Action (After Hot Questions)

**When:** Automatically appended to the bot's answer after HIGH or MEDIUM intent questions
**Purpose:** Leave a door open without being pushy

After a HIGH intent answer:
> 💼 *Thinking about getting started?* If you'd like to explore trading with a trusted broker, feel free to DM an admin — we're here to help. 🚀

After a MEDIUM intent answer:
> 📌 *If you ever want to take the next step and start live trading, just ask an admin — we'll point you in the right direction.*

---

### 1.6 Weekly Engagement Content (Approval Required)

**When:** Generated automatically each week, sent to **EBI Bot Management** for admin approval

| Day | Content | Time Generated |
|---|---|---|
| Monday | Week Ahead — Gold & Bitcoin outlook + key events | 8:00 AM |
| Wednesday | Mid-Week Education Tip (one concept, simply explained) | 8:00 AM |
| Friday | Week in Review — what happened + what's next | 8:00 AM |
| Saturday | Weekend Trading Mindset (discipline / risk / psychology) | 9:00 AM |

**Approval flow:**
1. Bot sends the content to EBI Bot Management group with two buttons: **✅ Approve & Post** and **❌ Reject**
2. Any admin taps the button
3. If approved → content is posted to the community group immediately
4. If rejected → nothing is posted, bot confirms rejection

---

### 1.7 Weekly Polls (Approval Required)

**When:** Every Monday at 8:15 AM, two poll ideas are sent to EBI Bot Management for approval
**Purpose:** Keep the group engaged and drive interaction from members who don't usually comment

The bot generates 2 ideas each week:
- **Poll 1** — Trading/market themed (e.g. "What's your Gold bias this week?")
- **Poll 2** — Fun/personality themed (e.g. "Which emotion destroys you most as a trader?")

Each is sent separately with its own Approve / Reject buttons so you can approve one and reject the other.

**Note:** The bot generates the question and options — you use Telegram's native poll feature to actually post it (or ask the bot to post it via the broadcast command).

---

### 1.8 Milestone DMs (30-Day Touch)

**When:** Daily at 10:00 AM, the bot checks for members who joined exactly 30 days ago
**What it sends:**
> Hey [Name]! You've been part of Elite by Infinity for a whole month — that's awesome! 🥳 We hope you've been getting value from the daily updates. Quick question: have you had a chance to explore live trading yet? If you're curious, just reply here — our admin team is happy to help. 💼

**Why:** A 30-day member is more comfortable, more educated, and more likely to convert than a brand new member. This touch creates a natural opening.

---

### 1.9 Re-Engagement DMs (21-Day Dormant)

**When:** Every Sunday at 11:00 AM, the bot checks for members who have been inactive (no Q&A) for 21+ days
**What it sends:** A friendly nudge reminding them the group is active and they're welcome to ask anything
**Limit:** Maximum 20 DMs per run to avoid spam. Each member only gets re-engaged once per 30-day period.

---

### 1.10 Rules Enforcement

**When:** Automatically on every group message (not just bot mentions)
**What it detects:** Spam, self-promotion, signal selling, scams, and misleading claims

**Strike system:**
- **Strike 1:** Public warning in the group ("this is your first warning")
- **Strike 2:** Final warning ("next violation will result in a mute")
- **Strike 3+:** Member is muted (internally flagged). Bot posts a public notice and sends a private alert to all admins with the user's ID and a ready-to-use `/unmute` command

**Examples of what triggers it:**
- "Join my signals group"
- "DM me for free signals"
- "I guarantee 100% profit"
- "Send Bitcoin to double your money"
- "Managed account available"

---

## Part 2 — Admin Commands

All commands below are **admin-only**. Non-admins who try them will see: ⛔ Not authorized.

To use a command, send it to the bot in a private DM or in the community group.

---

### Content Commands

#### `/broadcast <message>`
Posts your message directly to the community group, exactly as you type it.

**Example:**
```
/broadcast Markets are closed today for a public holiday. See you tomorrow! 🎉
```

#### `/announcement <message>`
Posts a formatted announcement with a header and EBI footer.

**Example:**
```
/announcement New trading sessions starting next Monday. Check pinned message for schedule.
```

**What it looks like in the group:**
```
📢 ANNOUNCEMENT
━━━━━━━━━━━━━━━━━━━━━━━

New trading sessions starting next Monday. Check pinned message for schedule.

━━━━━━━━━━━━━━━━━━━━━━━
— Elite by Infinity Team
```

---

### Pipeline Commands

#### `/pipeline`
Shows you the current conversion pipeline — who's hot, who's new, and what intent signals have been firing.

**What you'll see:**
- 🆕 New members in the last 48 hours (prime follow-up window)
- 🎯 High-intent members (score ≥ 3) from the last 7 days
- 📡 Most recent intent signals with their questions

**Use this every morning** as your daily brief before reaching out to potential clients.

---

### Moderation Commands

#### `/mute <user_id>`
Internally flags a user as muted. The bot will silently ignore all their messages (no AI responses, no violation warnings). They remain in the group.

**Example:** `/mute 123456789`

#### `/unmute <user_id>`
Removes the mute flag and resets their violation count to zero.

**Example:** `/unmute 123456789`

#### `/ban <user_id>`
Internally flags a user as banned. The bot completely ignores them (including rules enforcement).

**Example:** `/ban 123456789`

#### `/unban <user_id>`
Removes the ban flag and resets violations.

**Example:** `/unban 123456789`

**Important:** These are internal bot flags only. To actually remove someone from the group, you still use Telegram's native admin controls. The bot flags prevent the bot from interacting with them.

---

### Settings Commands

#### `/welcome on` / `/welcome off`
Enables or disables the automatic welcome messages (both public group and private DM).

**Use case:** Turn off before a planned group migration or if you're doing a test run.

#### `/pause`
Temporarily disables all AI Q&A responses. The bot stops answering questions but still enforces rules and sends welcome messages.

**Use case:** During a live trading session or important group event where you don't want bot interruptions.

#### `/resume`
Re-enables AI Q&A responses.

#### `/reload`
Re-reads the admin ID list from the server configuration file without needing to restart the bot. Use this when you add or remove an admin.

---

### Info & Testing Commands

#### `/stats`
Shows a summary dashboard:
- Total members in the database
- Messages sent by Market Bot (last 7 days)
- Messages sent by Community Bot (last 7 days)

#### `/testdm <user_id>`
Sends a test DM to any user ID to verify the bot can reach them.

**Example:** `/testdm 123456789`

**Use case:** Before sending the onboarding sequence or a milestone DM, you can verify the user hasn't blocked DMs from bots.

#### `/help`
Shows the full list of available admin commands.

---

### Public Commands (Any Member Can Use)

#### `/start`
Sends the member the welcome DM and registers them in the database. Useful if someone joined before the bot was active.

#### `/start_trading`
A conversion funnel command any member can type. The bot sends a 6-step guide to getting started with live trading (choose a broker → demo account → basics → fund → risk management → get support).

**This also triggers a HIGH-intent alert in EBI Potential Client Update**, so you know exactly who used it and when.

---

## Part 3 — Google Sheets

Two spreadsheets live in your EBI Drive folder.

### Sheet 1: EBI — New Member Tracker
Use this to manually track every new member and their journey from joining to converting.

**Columns:**
- Date Joined, Telegram ID, Username, First Name, Last Name
- DM Welcomed, Day 1 Sent, Day 3 Sent, Day 5 Sent (Yes/No dropdowns)
- Intent Score, Top Intent Signal
- Follow-Up Status (New → Contacted → Demo Opened → Live Account)
- Converted? (No / Demo / Live / Churned)
- Notes, Admin Assigned

**Summary tab** automatically calculates: total members, conversion rate, how many demos, how many live accounts.

### Sheet 2: EBI — Admin Conversion Dashboard
Four tabs:

| Tab | Purpose |
|---|---|
| 🎯 Intent Pipeline | Log every intent alert from Telegram here. Track follow-up. |
| 📅 Engagement Log | Record every piece of content posted, reactions, and performance. |
| 👤 Admin Activity | Track what each admin did — follow-ups, demos set up, etc. |
| 📊 KPI Scorecard | Weekly/monthly targets and actual numbers. |

**Key KPIs to track:**
- New members joined
- DM sequence completion rate
- Intent alerts generated
- Admin follow-up rate
- Demo accounts opened
- Live accounts converted
- Conversion rate %

---

## Part 4 — Security & Important Notes

### What the bot CANNOT do (by design)
- It cannot transfer money or access any trading accounts
- It cannot guarantee profits (it declines these questions automatically)
- It cannot read private messages between members
- It cannot approve its own content — a human admin must always approve weekly posts

### API Keys and Secrets
- All sensitive credentials are stored in the `.env` file on the server only
- Never share the `.env` file or post API keys in any Telegram group (including the management group)

### Bot requires admin status in the community group
The community bot must be made a group administrator for:
- Detecting when new members join (ChatMember updates)
- The bot does NOT need kick/ban permissions — those remain with human admins

### What to do if the bot goes down
1. Check the server logs (your tech team will have access)
2. Restart the bot: `python main.py`
3. The bot will resume exactly where it left off — all pending approvals are cleared (they are time-sensitive anyway), but all member records and intent scores are stored in Supabase and are not lost

---

## Part 5 — Weekly Admin Checklist

Run through this every Monday morning:

- [ ] Open **EBI Bot Management** group — approve or reject this week's Monday content and 2 poll ideas
- [ ] Open **EBI Potential Client Update** group — review new intent alerts from the weekend
- [ ] Open `/pipeline` in a bot DM — identify top leads to follow up today
- [ ] Update **EBI Admin Conversion Dashboard** with any follow-up outcomes from last week
- [ ] Check `/stats` — ensure bot activity is healthy
- [ ] Approve or reject Wednesday content (sent Tuesday evening)
- [ ] Approve or reject Friday content (sent Thursday evening)
- [ ] Approve or reject Weekend Mindset (sent Friday evening)

---

## Part 6 — Frequently Asked Questions

**Q: A member says they never received the welcome DM**
A: They likely have privacy settings that block DMs from unknown bots. Use `/testdm <their_user_id>` to confirm. Ask them to start a private chat with the bot using the /start command.

**Q: The bot isn't answering questions in the group**
A: Check if the bot is paused (use `/resume`). Also make sure members are tagging the bot (@BotUsername) or replying directly to one of its messages.

**Q: An admin got accidentally muted**
A: Use `/unmute <their_user_id>` from another admin account.

**Q: Can we change the weekly schedule?**
A: Yes — ask your tech team to update the cron schedule in `bots/community_bot.py`. No code logic changes needed, just the time values.

**Q: Can we change what the bot says in the onboarding sequence?**
A: Yes — the messages are in `services/onboarding.py`. Each day's message is a clearly labelled function that your tech team can edit.

**Q: How do I find a member's Telegram user ID?**
A: Forward any of their messages to @userinfobot on Telegram — it will show you their user ID.

---

*This document covers all features as of June 2026. Updated whenever new features are added.*
