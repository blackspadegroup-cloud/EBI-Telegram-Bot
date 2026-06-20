# Senior AI Engineer Prompt – Build 2 Telegram Bots for My Trading Community

You are a world-class Senior Software Engineer, AI Engineer, Product Manager, and Telegram Bot Developer.

Your mission is to design and build **two production-ready Telegram bots** for my trading community with clean architecture, excellent UX, and scalable code.

## General Requirements

* Language: Python (preferred) or Node.js
* Use Telegram Bot API
* Well-structured project with modular code
* Easy to deploy on VPS or Docker
* Include `.env` configuration
* Include installation guide and documentation
* Handle errors gracefully
* Maintain logs for debugging
* Avoid duplicate messages
* Support future expansion

---

# BOT 1 – AI Market Analysis Bot

## Objective

Automatically provide concise and useful market updates focused on:

* XAUUSD (Gold)
* Bitcoin (BTC)

The bot should research reliable online sources and summarize information using AI before posting to the Telegram group.

## Scheduled Updates

Post automatically every day at:

* 7:00 AM
* 2:00 PM
* 7:00 PM

(Timezone should be configurable.)

## Content Requirements

Each update should include:

### Gold Section

* Latest macro news
* Major economic developments
* Central bank updates
* Market sentiment
* Technical bias (Bullish / Bearish / Neutral)

### Bitcoin Section

* Crypto market news
* ETF or institutional developments
* Regulatory updates
* Whale activity if significant
* Overall sentiment

## Important News Monitoring

The bot should continuously monitor for breaking events.

If there is high-impact news, it should immediately post an alert without waiting for scheduled times.

Examples:

* US CPI
* FOMC
* NFP
* Interest Rate Decision
* PPI
* GDP
* Employment Data
* Major Fed speeches
* Geopolitical events affecting Gold or BTC

## Economic Calendar Monitoring

Monitor red-folder/high-impact economic events and notify the Telegram group before and after release.

Example:

🚨 HIGH IMPACT EVENT
US CPI will be released in 30 minutes.

Potential volatility expected for Gold and Bitcoin.

## Message Format

Keep updates extremely concise.

### English (maximum 3 sentences)

Example:

**Gold Update 🇺🇸**
US Dollar weakens after softer economic data, providing support for Gold. Traders remain cautious ahead of CPI. Short-term sentiment: mildly bullish.

### Chinese (maximum 3 sentences)

Example:

**黄金更新 🇨🇳**
美元因经济数据疲弱而走软，为黄金提供支撑。市场关注即将公布的 CPI 数据。短线情绪偏多。

Do the same for Bitcoin.

Use emojis appropriately but keep messages professional.

---

# Senior AI Engineer Prompt – Build an AI Telegram Community Assistant Bot

You are a world-class Senior Software Engineer, AI Engineer, Product Manager, and Telegram Bot Developer.

Your mission is to build a **production-ready AI Community Assistant Bot** for my Telegram trading group. The bot should make the community feel active, welcoming, educational, and professionally managed while reducing the workload of human admins.

## Core Objectives

The bot should:

* Welcome new members.
* Engage with members naturally.
* Answer frequently asked questions.
* Privately onboard new users.
* Assist admins by automating repetitive tasks.
* Create a friendly and valuable community experience.

---

# 1. Welcome New Members

When a user joins the Telegram group:

* Automatically send a warm welcome message in the group.
* Mention the user's name or @username.
* Encourage them to introduce themselves and participate.

Example:

🎉 Welcome, @username!

We're excited to have you join our trading community. Feel free to introduce yourself, ask questions, and learn together with everyone here. Wishing you success on your trading journey!

---

# 2. Private Onboarding Message

Immediately after a member joins, send them a direct message.

The message should:

* Thank them for joining.
* Introduce the AI assistant.
* Explain what help is available.
* Encourage them to ask questions anytime.

Example:

Hi! 👋 Welcome to our trading community.

I'm your AI assistant and I'm here to help with:

* Gold (XAUUSD)
* Bitcoin (BTC)
* Trading basics
* Risk management
* Economic news
* Community information

Feel free to message me anytime if you have questions. Enjoy your stay!

---

# 3. AI Question & Answer Assistant

The bot should intelligently answer member questions related to:

* Forex trading
* Gold (XAUUSD)
* Bitcoin (BTC)
* Trading terminology
* Risk management
* Trading psychology
* Economic indicators (CPI, FOMC, NFP, etc.)
* Basic technical analysis
* Market concepts
* Community rules
* Beginner education
* Frequently asked questions

## Response Style

* Friendly and professional.
* Easy to understand.
* Short and concise.
* Educational rather than promotional.
* Never guarantee profits or winning trades.
* Clearly state when information is uncertain instead of making things up.

---

# 4. Bilingual Support

When appropriate, answer in both:

* 🇬🇧 Simple English
* 🇨🇳 Simplified Chinese

Keep each language section brief and easy to read.

---

# 5. Community Engagement

The bot should proactively improve engagement by:

* Greeting members at appropriate times.
* Congratulating milestones when configured.
* Encouraging respectful discussions.
* Suggesting educational topics.
* Sharing beginner-friendly trading tips when requested.

The bot should never spam the group.

---

# 6. Community Rules Enforcement

If members violate group rules, politely remind them to:

* Stay respectful.
* Avoid scams.
* Avoid excessive self-promotion.
* Stay on topic.
* Refrain from posting misleading financial claims.

The bot should escalate repeated violations to admins rather than arguing.

---

# 7. Admin Commands

Create secure admin-only commands such as:

* /help
* /broadcast
* /announcement
* /stats
* /welcome on
* /welcome off
* /mute
* /unmute
* /ban
* /unban
* /reload
* /testdm

Only authorized Telegram user IDs should be allowed to execute these commands.

---

# 8. Logging & Analytics

Track useful metrics such as:

* Total members joined.
* Daily joins.
* Number of questions answered.
* Most common FAQ topics.
* Private welcome messages sent.
* Bot uptime and errors.

Store logs for troubleshooting.

---

# 9. Security & Privacy

* Never expose API keys or secrets.
* Validate all user input.
* Respect Telegram rate limits.
* Prevent spam loops.
* Keep private conversations confidential.
* Fail gracefully with meaningful error logs.

---

# 10. Future Expansion

Design the architecture so the bot can later support:

* AI-powered trade explanations.
* TradingView alert notifications.
* Market news summaries.
* Multi-language support beyond English and Chinese.
* CRM integration.
* User segmentation and tagging.
* Gamification and leaderboards.
* Quiz and educational modules.
* Referral tracking.
* Integration with websites or mobile apps.

---

# Deliverables

Provide:

1. A scalable project architecture.
2. Clean folder structure.
3. Full commented source code.
4. Environment variable (`.env`) template.
5. Database schema if required.
6. Docker deployment files.
7. VPS deployment guide.
8. Testing checklist.
9. Security recommendations.
10. Ideas to make the bot more engaging, reliable, and valuable for a trading community with thousands of members.

Build this as a production-grade system with maintainability, performance, and an excellent user experience as top priorities.

