"""
services/i18n.py – Bilingual content + per-user language preference.

The community bot supports two languages: English ("en") and Simplified
Chinese ("zh"). A member chooses their language after /start (or via /language),
and the whole conversation — menus, onboarding, CTAs, and AI answers — is then
served in that single language.

Language preference is stored in the existing bot_state table:
    key = "lang:{telegram_id}", value = "en" | "zh"

Usage:
    from services.i18n import t, get_lang, set_lang
    text = t("welcome_dm", get_lang(user_id), name=user.first_name)
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import config
from database import get_state, set_state

DEFAULT_LANG = "en"
SUPPORTED = ("en", "zh")
LANG_NAME = {"en": "English", "zh": "Simplified Chinese"}


# ── Preference store ──────────────────────────────────────────────────────────

def get_lang(telegram_id: int) -> str:
    val = get_state(f"lang:{telegram_id}", DEFAULT_LANG)
    return val if val in SUPPORTED else DEFAULT_LANG


def set_lang(telegram_id: int, lang: str) -> None:
    if lang in SUPPORTED:
        set_state(f"lang:{telegram_id}", lang)


def lang_is_set(telegram_id: int) -> bool:
    """True if the member has explicitly chosen a language."""
    return get_state(f"lang:{telegram_id}", None) in SUPPORTED


# ── Translation helper ────────────────────────────────────────────────────────

def t(key: str, lang: str = "en", **kwargs) -> str:
    entry = STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("en") or ""
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


# ── Keyboards ─────────────────────────────────────────────────────────────────

def language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en"),
        InlineKeyboardButton("🇨🇳 中文", callback_data="setlang:zh"),
    ]])


def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_about", lang), callback_data="menu:about")],
        [InlineKeyboardButton(t("btn_how", lang), callback_data="menu:how")],
        [InlineKeyboardButton(t("btn_guide", lang), callback_data="menu:guide")],
        [InlineKeyboardButton(t("btn_book", lang), callback_data="menu:book")],
        [
            InlineKeyboardButton(t("btn_ask", lang), callback_data="menu:ask"),
            InlineKeyboardButton(t("btn_lang", lang), callback_data="menu:lang"),
        ],
    ])


def back_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t("btn_back", lang), callback_data="menu:home"),
    ]])


def how_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_book", lang), callback_data="menu:book")],
        [InlineKeyboardButton(t("btn_back", lang), callback_data="menu:home")],
    ])


def booking_kb(lang: str) -> InlineKeyboardMarkup:
    rows = []
    if config.BOOKING_URL:
        rows.append([InlineKeyboardButton(t("btn_pick_time", lang), url=config.BOOKING_URL)])
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


# ── String table ──────────────────────────────────────────────────────────────
# Keep Markdown simple: only balanced *bold*. Avoid underscores to prevent
# legacy-Markdown parse errors.

STRINGS = {
    "language_prompt": {
        "en": (
            "👋 Welcome to Elite by Infinity!\n"
            "Please choose your language:\n\n"
            "👋 欢迎加入 Elite by Infinity！\n"
            "请选择您的语言："
        ),
        "zh": (
            "👋 Welcome to Elite by Infinity!\n"
            "Please choose your language:\n\n"
            "👋 欢迎加入 Elite by Infinity！\n"
            "请选择您的语言："
        ),
    },

    "language_changed": {
        "en": "✅ Language set to English.",
        "zh": "✅ 语言已设为中文。",
    },

    "welcome_dm": {
        "en": (
            "Hi {name}! 👋\n\n"
            "Welcome to *Elite by Infinity* — your premium Gold (XAUUSD) & Bitcoin trading community.\n\n"
            "I'm your AI assistant. Use the menu below to learn what we do, grab your free starter guide, "
            "or book a free 1-on-1 with our team. You can also just message me any trading question anytime. 🚀"
        ),
        "zh": (
            "你好 {name}！👋\n\n"
            "欢迎加入 *Elite by Infinity* —— 你的高端黄金（XAUUSD）与比特币交易社群。\n\n"
            "我是你的 AI 助手。用下面的菜单了解我们、领取免费新手指南，或预约与团队的免费 1 对 1。"
            "你也可以随时直接问我任何交易问题。🚀"
        ),
    },

    "menu_title": {
        "en": "What would you like to do? 👇",
        "zh": "你想做什么？👇",
    },

    # Menu buttons
    "btn_about": {"en": "ℹ️ About EBI", "zh": "ℹ️ 关于 EBI"},
    "btn_how": {"en": "🧭 How It Works", "zh": "🧭 运作方式"},
    "btn_guide": {"en": "🎁 Free Starter Guide", "zh": "🎁 免费新手指南"},
    "btn_book": {"en": "📅 Book a Free 1-on-1", "zh": "📅 预约免费 1 对 1"},
    "btn_ask": {"en": "💬 Ask a Question", "zh": "💬 提问"},
    "btn_lang": {"en": "🌐 Language", "zh": "🌐 语言"},
    "btn_back": {"en": "⬅️ Back to Menu", "zh": "⬅️ 返回菜单"},
    "btn_pick_time": {"en": "📅 Pick a time", "zh": "📅 选择时间"},

    "about_ebi": {
        "en": (
            "🏆 *About Elite by Infinity*\n\n"
            "We're a premium trading community for Gold (XAUUSD) and Bitcoin — built on discipline, "
            "real education, and zero hype.\n\n"
            "What you get:\n"
            "• Daily market analysis & breaking-news alerts\n"
            "• Structured education from beginner to confident trader\n"
            "• 1-on-1 coaching from people who actually trade\n"
            "• A supportive community on the same journey\n\n"
            "We don't sell dreams or guarantee profits. We teach you to trade properly and manage risk — "
            "the skills that actually last. Ready to see how it works? 👇"
        ),
        "zh": (
            "🏆 *关于 Elite by Infinity*\n\n"
            "我们是专注黄金（XAUUSD）与比特币的高端交易社群 —— 以纪律、真材实料的教育、零浮夸为核心。\n\n"
            "你会得到：\n"
            "• 每日市场分析与突发新闻提醒\n"
            "• 从新手到稳健交易者的系统化教育\n"
            "• 由真正在交易的人提供 1 对 1 指导\n"
            "• 一群同行路上的伙伴\n\n"
            "我们不卖梦想，也不保证盈利。我们教你正确交易、管理风险 —— 这些才是真正能长久的技能。"
            "想看看怎么运作？👇"
        ),
    },

    "how_it_works": {
        "en": (
            "🧭 *How It Works*\n\n"
            "*1. Learn* — Follow our daily updates and starter lessons. Ask me anything, anytime.\n\n"
            "*2. Practise* — Start on a demo account and build skill with no risk.\n\n"
            "*3. Go live* — When you're ready, our team guides you 1-on-1 through setup and your first "
            "real trade (from as little as $100).\n\n"
            "*4. Grow* — Keep learning with the community and sharpen your edge.\n\n"
            "No pressure, no rush — we move at your pace. 🚀"
        ),
        "zh": (
            "🧭 *运作方式*\n\n"
            "*1. 学习* —— 跟着每日更新和新手课程，随时向我提问。\n\n"
            "*2. 练习* —— 先用模拟账户，无风险地打磨技能。\n\n"
            "*3. 实盘* —— 准备好后，团队会 1 对 1 带你设置账户并完成第一笔真实交易（最低 $100 起）。\n\n"
            "*4. 成长* —— 在社群里持续学习，磨利你的优势。\n\n"
            "没有压力、不催促 —— 按你的节奏来。🚀"
        ),
    },

    "lead_magnet": {
        "en": (
            "🎁 *Your Free Gold & Bitcoin Starter Kit*\n\n"
            "The 5 fundamentals every new trader must master:\n\n"
            "*1. What moves the market* — Gold follows the US Dollar, interest rates and global fear. "
            "Bitcoin follows liquidity, ETF flows and sentiment.\n"
            "*2. Risk first* — Never risk more than 1–2% of your account on one trade. Set your stop loss "
            "before you enter.\n"
            "*3. Position sizing* — Your lot size, not your entry, decides if you survive. Size small.\n"
            "*4. One setup at a time* — Master one strategy before adding more. Consistency beats variety.\n"
            "*5. Journal everything* — Review your trades weekly. The market is the best (and most expensive) teacher.\n\n"
            "Want a *free 1-on-1 session* to apply this to your own plan? Reply with your *name* and we'll "
            "set it up — no cost, no pressure. 🙌"
        ),
        "zh": (
            "🎁 *你的免费黄金与比特币新手包*\n\n"
            "每位新手必须掌握的 5 个基础：\n\n"
            "*1. 什么在推动市场* —— 黄金跟随美元、利率和全球避险情绪；比特币跟随流动性、ETF 资金流和市场情绪。\n"
            "*2. 风险第一* —— 单笔交易风险不超过账户的 1–2%，进场前就设好止损。\n"
            "*3. 仓位管理* —— 决定你能否生存的是仓位大小，而不是进场点。仓位要小。\n"
            "*4. 一次只练一个策略* —— 先精通一个再加新的。稳定胜过花样。\n"
            "*5. 记录每一笔* —— 每周复盘。市场是最好（也最贵）的老师。\n\n"
            "想要一次*免费 1 对 1*，把这些用到你自己的计划上吗？回复你的*名字*，我们就帮你安排 —— 免费、无压力。🙌"
        ),
    },

    "book_call": {
        "en": (
            "📅 *Book Your Free 1-on-1*\n\n"
            "Sit down with a member of our team — we'll answer your questions, look at your goals, and map "
            "out your next step. No cost, no obligation.\n\n"
            "Tap below to book a time, or reply with your *name* and we'll arrange it for you. 🙌"
        ),
        "zh": (
            "📅 *预约你的免费 1 对 1*\n\n"
            "和我们的团队成员聊一聊 —— 解答你的疑问、了解你的目标，帮你规划下一步。免费、无义务。\n\n"
            "点击下方预约时间，或回复你的*名字*，我们帮你安排。🙌"
        ),
    },

    "ask_hint": {
        "en": (
            "💬 Just type your question below — Gold, Bitcoin, trading basics, risk management, or anything else. "
            "I'll answer in English. 🙌"
        ),
        "zh": (
            "💬 直接在下面输入你的问题 —— 黄金、比特币、交易基础、风险管理，什么都行。我会用中文回答。🙌"
        ),
    },

    "capture_thanks": {
        "en": (
            "🙏 Thank you! Our team has your request and will reach out personally to arrange your free "
            "1-on-1. In the meantime, feel free to ask me anything about Gold, Bitcoin, or getting started."
        ),
        "zh": (
            "🙏 谢谢！我们的团队已收到你的请求，会亲自联系你安排免费 1 对 1。在那之前，关于黄金、比特币或如何开始，随时问我。"
        ),
    },

    "declined_topic": {
        "en": (
            "⚠️ I can't give specific trading signals or financial advice.\n\n"
            "I'm here to educate — not to tell you when to buy or sell. Always do your own research and "
            "manage your risk! 🙏"
        ),
        "zh": (
            "⚠️ 我不能提供具体的买卖信号或投资建议。\n\n"
            "我是来做教育的 —— 不会告诉你何时买卖。请务必做好自己的研究，管理好风险！🙏"
        ),
    },

    "rate_limited": {
        "en": (
            "⏳ You've asked a lot of questions recently! Please wait a bit — I want to make sure everyone "
            "gets help. 🙏"
        ),
        "zh": (
            "⏳ 你最近问得有点多啦！请稍等一下 —— 我想确保每个人都能得到帮助。🙏"
        ),
    },

    "ai_fallback": {
        "en": "I couldn't process your question right now. Please try again in a moment! 🙏",
        "zh": "我现在无法处理你的问题，请稍后再试一次！🙏",
    },

    # Onboarding Day 1
    "onboarding_day1": {
        "en": (
            "Hey {name}! 👋\n\n"
            "Gold trading in 60 seconds 🥇\n\n"
            "Gold (XAUUSD) moves on 3 key forces:\n\n"
            "1. The US Dollar — when USD weakens, Gold rises. They move opposite.\n"
            "2. Interest rates — lower rates make Gold more attractive than bonds.\n"
            "3. Global fear — war, crisis and uncertainty push investors into Gold as a safe haven.\n\n"
            "This is why every major event — CPI, FOMC, NFP — moves Gold: they all affect the dollar and "
            "rate expectations.\n\n"
            "Next time Gold moves, ask: which of these 3 is driving it? That one question makes you sharper "
            "than 90% of beginners.\n\n"
            "More on Day 3. Stay disciplined. 📈\n— Elite by Infinity"
        ),
        "zh": (
            "你好 {name}！👋\n\n"
            "60 秒看懂黄金 🥇\n\n"
            "黄金（XAUUSD）主要由 3 股力量推动：\n\n"
            "1. 美元 —— 美元走弱，黄金上涨，两者反向。\n"
            "2. 利率 —— 利率越低，黄金比债券更有吸引力。\n"
            "3. 全球避险 —— 战争、危机、不确定性会让资金涌入黄金避险。\n\n"
            "这就是为什么每个重要数据 —— CPI、FOMC、非农 —— 都会牵动黄金：它们都影响美元和利率预期。\n\n"
            "下次黄金波动时问问自己：是这 3 个里的哪一个在推动？这一个问题，就能让你比 90% 的新手更敏锐。\n\n"
            "第 3 天再聊。保持纪律。📈\n— Elite by Infinity"
        ),
    },

    # Onboarding Day 3
    "onboarding_day3": {
        "en": (
            "Hey {name} 👋\n\n"
            "The #1 mistake new traders make — and it's not a bad entry. 🚨\n\n"
            "It's trading without a stop loss.\n\n"
            "Gold can move 300–500 pips in a single news event. Without a stop loss, one wrong trade can wipe "
            "out weeks of gains in minutes.\n\n"
            "The rule every professional lives by:\n"
            "➡️ Never risk more than 1–2% of your account on a single trade\n"
            "➡️ Set your stop loss before you enter — not after\n"
            "➡️ If you can't define your risk, you're not trading. You're gambling.\n\n"
            "Risk management isn't the boring part — it's what keeps you alive long enough to profit.\n\n"
            "Questions? Just reply here. 🙏\n— Elite by Infinity"
        ),
        "zh": (
            "你好 {name} 👋\n\n"
            "新手最大的错误 —— 而且不是进场点不好。🚨\n\n"
            "是不设止损就交易。\n\n"
            "黄金在一个数据里就能波动 300–500 点。没有止损，一笔错单几分钟就能吞掉你几周的盈利。\n\n"
            "每个专业交易者都遵守的规则：\n"
            "➡️ 单笔交易风险绝不超过账户的 1–2%\n"
            "➡️ 进场前就设好止损 —— 不是进场后\n"
            "➡️ 如果你说不出自己的风险，那不是交易，是赌博。\n\n"
            "风险管理不是无聊的部分 —— 它能让你活得够久，久到能盈利。\n\n"
            "有问题？直接回复我。🙏\n— Elite by Infinity"
        ),
    },

    # Onboarding Day 5
    "onboarding_day5": {
        "en": (
            "Hey {name}! 👋\n\n"
            "5 days in Elite by Infinity — hope the daily updates have been useful. 🙌\n\n"
            "Quick question: are you thinking about live trading?\n\n"
            "If yes, here's what to know:\n"
            "✅ You can start with as little as $100 through AIMS FX, our recommended broker\n"
            "✅ You don't have to figure it out alone — our team provides 1-on-1 education\n"
            "✅ We walk you through everything: account setup, platform, your first trade\n"
            "✅ No hidden fees. No pressure. Just real guidance from people who trade.\n\n"
            "When you're ready, just reply here — a team member will reach out personally. No rush. 💼\n"
            "— Elite by Infinity 🥇"
        ),
        "zh": (
            "你好 {name}！👋\n\n"
            "加入 Elite by Infinity 5 天了 —— 希望每日更新对你有帮助。🙌\n\n"
            "想问一句：你有在考虑实盘交易吗？\n\n"
            "如果有，这些你应该知道：\n"
            "✅ 通过我们推荐的经纪商 AIMS FX，最低 $100 就能开始\n"
            "✅ 你不必一个人摸索 —— 我们团队提供 1 对 1 教学\n"
            "✅ 从开户、平台到第一笔交易，我们一步步带你\n"
            "✅ 没有隐藏费用，没有压力，只有真正在交易的人给你的真实指导。\n\n"
            "等你准备好，直接回复我 —— 团队成员会亲自联系你。不急。💼\n"
            "— Elite by Infinity 🥇"
        ),
    },

    "soft_cta_high": {
        "en": (
            "\n\n💼 Interested in starting live trading? We work with AIMS FX — a trusted broker with a $100 "
            "minimum deposit. More importantly, our team offers 1-on-1 education to guide you from zero to "
            "your first live trade. Reply here and an admin will reach out personally. 🚀"
        ),
        "zh": (
            "\n\n💼 想开始实盘交易吗？我们合作的是 AIMS FX —— 受信赖的经纪商，最低入金 $100。更重要的是，"
            "我们团队提供 1 对 1 教学，带你从零到第一笔实盘交易。回复这里，管理员会亲自联系你。🚀"
        ),
    },

    "soft_cta_medium": {
        "en": (
            "\n\n📌 When you're ready to take the next step, our team is here. We offer 1-on-1 guidance for "
            "new traders through AIMS FX — no pressure, just real support. Feel free to ask an admin anytime."
        ),
        "zh": (
            "\n\n📌 等你准备好迈出下一步，我们的团队都在。我们通过 AIMS FX 为新手提供 1 对 1 指导 —— "
            "没有压力，只有实实在在的支持。随时可以问管理员。"
        ),
    },

    "milestone_dm": {
        "en": (
            "Hey {name}! 🎉\n\n"
            "You've been part of Elite by Infinity for a whole month — that's awesome! 🥳\n\n"
            "We hope the daily market updates and community have been valuable. 📊\n\n"
            "Quick question: have you had a chance to explore live trading yet? If you're curious about "
            "getting started, just reply here — happy to guide you. 💼\n\n"
            "Keep learning, stay disciplined, and enjoy the journey! 🚀"
        ),
        "zh": (
            "你好 {name}！🎉\n\n"
            "你加入 Elite by Infinity 整整一个月啦 —— 太棒了！🥳\n\n"
            "希望每日的市场更新和社群对你很有价值。📊\n\n"
            "想问一句：你有机会尝试实盘交易了吗？如果想了解怎么开始，直接回复我 —— 我很乐意带你。💼\n\n"
            "持续学习，保持纪律，享受这段旅程！🚀"
        ),
    },

    "reengagement_dm": {
        "en": (
            "Hey {name}! 👋\n\n"
            "It's been a while since we've seen you around Elite by Infinity — we miss you! 😊\n\n"
            "Gold and Bitcoin have been very active lately with major events moving the markets. Come back "
            "and join the conversation! 📊\n\n"
            "If there's anything you'd like to learn, I'm always here. Just send me a message anytime. 🙌"
        ),
        "zh": (
            "你好 {name}！👋\n\n"
            "好久没在 Elite by Infinity 见到你了 —— 我们想你了！😊\n\n"
            "最近黄金和比特币都很活跃，有不少大事件在牵动市场。回来一起聊聊吧！📊\n\n"
            "如果有什么想学的，我一直都在。随时给我发消息。🙌"
        ),
    },

    "lead_alert_guide": {
        "en": "🎁 Lead grabbed the *Free Starter Guide*",
        "zh": "🎁 Lead grabbed the *Free Starter Guide*",
    },
    "lead_alert_book": {
        "en": "📅 Lead requested a *1-on-1 booking*",
        "zh": "📅 Lead requested a *1-on-1 booking*",
    },
}


# ── Start-trading guide (longer; built per language) ──────────────────────────

def start_trading_text(lang: str) -> str:
    if lang == "zh":
        return (
            "🚀 *实盘交易入门指南*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "从零到第一笔交易的简单路径：\n\n"
            "*第 1 步 — 选择受监管的经纪商* 🏦\n"
            "优先选受 FCA、ASIC、CySEC 或 MAS 监管的平台。监管能保护你的资金。可以问管理员要可信推荐。\n\n"
            "*第 2 步 — 先开模拟账户* 🎮\n"
            "用虚拟资金练习，再投入真钱。大多数经纪商提供免费、无期限的模拟账户。\n\n"
            "*第 3 步 — 打好基础* 📚\n"
            "理解：手数、止损、止盈、点值和杠杆。有不懂的随时问我。\n\n"
            "*第 4 步 — 入金* 💳\n"
            "从小做起，大多数平台 $100–$500 即可。永远不要投入你输不起的钱。\n\n"
            "*第 5 步 — 风险管理优先* 🛡️\n"
            "单笔最多冒险 1–2%。进场前就设好止损。保护本金 —— 它是你最重要的交易工具。\n\n"
            "*第 6 步 — 获得支持* 🤝\n"
            "我们的团队随时为你引导。随时私信我们 —— 没有压力，没有义务，只有真诚的帮助。\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ 交易有风险。永远不要投入超过你能承受的资金。"
        )
    return (
        "🚀 *Getting Started with Live Trading*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "A simple path from zero to your first trade:\n\n"
        "*Step 1 — Choose a Regulated Broker* 🏦\n"
        "Look for brokers regulated by FCA, ASIC, CySEC or MAS. Regulation protects your funds. "
        "Ask our admins for trusted recommendations.\n\n"
        "*Step 2 — Open a Demo Account First* 🎮\n"
        "Practise with virtual money before risking real capital. Most brokers offer free demo accounts.\n\n"
        "*Step 3 — Learn the Basics* 📚\n"
        "Understand: lot sizes, stop loss, take profit, pip value and leverage. Ask me anything.\n\n"
        "*Step 4 — Fund Your Account* 💳\n"
        "Start small — most brokers accept $100–$500. Never deposit money you can't afford to lose.\n\n"
        "*Step 5 — Risk Management First* 🛡️\n"
        "Max 1–2% risk per trade. Set your stop loss before you enter. Protect your capital.\n\n"
        "*Step 6 — Get Support* 🤝\n"
        "Our team is here to guide you. DM us anytime — no pressure, no obligation, just honest help.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Trading involves risk. Never invest more than you can afford to lose."
    )
