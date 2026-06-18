# EBI Telegram Bots

Two production-ready Telegram bots for the **Elite by Infinity** trading community.

| Bot | Purpose |
|-----|---------|
| **Market Bot** | AI market updates for Gold & Bitcoin at 7AM / 2PM / 7PM SGT + breaking news |
| **Community Bot** | Welcome new members, answer trading questions via AI |

---

## Quick Start (15 minutes)

### Step 1 – Create your two Telegram bots

1. Open Telegram and message **@BotFather**
2. Send `/newbot` → name it `EBI Market Bot` → username e.g. `ebi_market_bot`
3. Copy the token — this is your `MARKET_BOT_TOKEN`
4. Send `/newbot` again → name it `EBI Community` → username e.g. `ebi_community_bot`
5. Copy the token — this is your `COMMUNITY_BOT_TOKEN`

### Step 2 – Get your Group IDs

1. Add both bots to your Telegram group(s) as **admins** (required for welcome messages)
2. Forward any group message to **@userinfobot** → it shows the group chat ID (negative number)
3. This is your `MARKET_GROUP_ID` and `COMMUNITY_GROUP_ID`

### Step 3 – Get Google Gemini API Key (FREE)

1. Go to https://aistudio.google.com/app/apikey
2. Click **Create API Key**
3. Copy it → this is your `GEMINI_API_KEY`
> Free tier: 15 requests/minute, 1 million tokens/day — plenty for this bot.

### Step 4 – Get your Supabase credentials

1. Go to your Supabase project dashboard → **Settings → API**
2. Copy the **Project URL** → `SUPABASE_URL`
3. Copy the **service_role** key (not anon key) → `SUPABASE_KEY`
> Use service_role so the bot can bypass RLS policies.

### Step 5 – Optional: Free news API keys

- **NewsAPI** (improves news quality): https://newsapi.org → 100 free req/day
- **CryptoPanic** (better crypto news): https://cryptopanic.com/developers/api/

### Step 6 – Configure your .env file

```bash
cp .env.example .env
# Edit .env with your values
```

---

## Deployment Options

### Option A: Railway.app (Recommended – Free)

Railway gives you $5/month free credits — enough to run both bots 24/7.

1. Push your code to a GitHub repo (never commit `.env`!)
2. Go to https://railway.app → **New Project → Deploy from GitHub**
3. Select your repo
4. Go to **Variables** tab → add all your `.env` variables
5. Railway auto-detects the Dockerfile and deploys

Your bots will be live in ~2 minutes.

### Option B: Docker on VPS (Ubuntu/Debian)

```bash
# 1. SSH into your VPS
ssh user@your-server-ip

# 2. Install Docker
curl -fsSL https://get.docker.com | sh

# 3. Clone/upload your project
git clone your-repo
cd "EBI Telegram Bot"

# 4. Configure environment
cp .env.example .env
nano .env   # fill in all values

# 5. Start
docker compose up -d

# 6. Check logs
docker compose logs -f
```

### Option C: Run locally (for testing)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env

# Run
python main.py
```

---

## Project Structure

```
EBI Telegram Bot/
├── main.py                  # Entry point – runs both bots
├── config.py                # All settings from .env
├── database.py              # Supabase client + all DB queries
├── bots/
│   ├── market_bot.py        # Bot 1: Market Analysis
│   └── community_bot.py     # Bot 2: Community Assistant
├── services/
│   ├── ai.py                # Google Gemini integration
│   ├── news.py              # RSS + NewsAPI + CryptoPanic
│   ├── prices.py            # Gold & BTC prices (yfinance)
│   ├── calendar.py          # Economic calendar (Forex Factory)
│   └── formatter.py         # Message formatting helpers
├── utils/
│   └── logger.py            # Rotating file + console logs
├── logs/                    # Auto-created, rotating log files
├── .env.example             # Copy this to .env
├── Dockerfile
├── docker-compose.yml
└── railway.toml             # Railway.app deployment config
```

---

## Admin Commands

Both bots respond to these commands — but **only from your ADMIN_IDS**.

| Command | Bot | Description |
|---------|-----|-------------|
| `/testnews` | Market | Trigger an update right now |
| `/pause` | Both | Stop all automatic messages |
| `/resume` | Both | Resume automatic messages |
| `/stats` | Both | Members count + message stats |
| `/broadcast <message>` | Both | Send announcement to the group |
| `/help` | Both | List available commands |

---

## Schedule (Asia/Singapore, UTC+8)

| Time | Action |
|------|--------|
| 07:00 | Market update posted to group |
| 14:00 | Market update posted to group |
| 19:00 | Market update posted to group |
| Every 15 min | Breaking news scan |
| Every 30 min | Economic calendar check |

---

## Database Tables Used

| Table | Source | Purpose |
|-------|--------|---------|
| `telegram_subscribers` | Existing | Member tracking |
| `telegram_messages` | Existing | Message audit log |
| `bot_sent_news` | New (created) | News deduplication |
| `bot_state` | New (created) | Runtime state (pause/resume, alert keys) |
| `bot_qa_interactions` | New (created) | Q&A history |

---

## Testing Checklist

- [ ] `/testnews` from admin account triggers an update in the group
- [ ] Market update includes Gold price, BTC price, bilingual summary
- [ ] New member joining the group gets a public welcome + private DM
- [ ] Asking the community bot a trading question gets a response
- [ ] Admin-only commands rejected for non-admins
- [ ] `/pause` stops posts; `/resume` restarts them
- [ ] `/broadcast hello everyone` posts to the group
- [ ] Check `logs/ebi_bots.log` for errors
- [ ] Supabase `telegram_subscribers` gets new row when member joins
- [ ] Supabase `bot_qa_interactions` gets new row after Q&A

---

## Security Notes

- Never commit your `.env` file — it's in `.gitignore`
- Use the Supabase `service_role` key (server-side only, never in frontend)
- Admin commands are restricted by Telegram user ID — not just username
- Bot runs as non-root user inside Docker
- All secrets are environment variables — nothing hardcoded

---

## Future Expansion (Architecture Ready)

The modular structure supports adding:
- **TradingView webhooks** → new endpoint in a `webhooks/` module
- **Forex signals** → new `services/signals.py`
- **Multi-language** → extend `services/ai.py` prompts
- **Discord/WhatsApp** → parallel `bots/discord_bot.py` using same services
- **Analytics dashboard** → query `bot_qa_interactions` + `telegram_messages`

---

## Troubleshooting

**Bot not responding:**
- Check logs: `docker compose logs -f`
- Verify `MARKET_BOT_TOKEN` and `COMMUNITY_BOT_TOKEN` are correct
- Make sure both bots are added to the group as admins

**Welcome messages not working:**
- Community bot must be a group **admin** with "Manage Members" permission
- Telegram requires this to receive `chat_member` updates

**AI not generating content:**
- Verify `GEMINI_API_KEY` at https://aistudio.google.com
- Check Gemini free tier limits (15 RPM, 1M tokens/day)

**Database errors:**
- Use the `service_role` key, not `anon` key, for `SUPABASE_KEY`
- Check Supabase project is ACTIVE_HEALTHY in the dashboard
