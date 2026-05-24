"""
Nepal News Telegram Bot
------------------------
Sends daily news digests from eKantipur, Kathmandu Post, and Annapurna.
Users choose their preferred time (9AM, 12PM, 6PM) and categories.

Requirements:
    pip install python-telegram-bot apscheduler

Setup:
    1. Create a bot via @BotFather on Telegram, get the token
    2. Set BOT_TOKEN below
    3. Run: python bot.py
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, JobQueue
)
from botdata import token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────

BOT_TOKEN = token

# Database files per outlet
OUTLETS = {
    "ekantipur":       "Article.db",
    "kathmandu_post":  "TheKtmPost.db",
    "annapurna":       "AnnapurnaArticle.db",
}

OUTLET_LABELS = {
    "ekantipur":      "eKantipur 📰",
    "kathmandu_post": "Kathmandu Post 📰",
    "annapurna":      "Annapurna Post 📰",
}

CATEGORIES = [
    "all",
    "politics",
    "business",
    "sports",
    "entertainment",
    "world",
    "opinion",
    "national",
    "valley",
    "feature",
    "interview",
    "art_culture",
    "money",
]

SEND_TIMES = {
    "9AM":  {"hour": 9,  "minute": 0},
    "12PM": {"hour": 12, "minute": 0},
    "6PM":  {"hour": 18, "minute": 0},
}

# In-memory user preferences store
# Structure: { chat_id: { "time": "9AM", "categories": ["politics", "sports"], "outlets": ["ekantipur"], "sent": set() } }
USER_PREFS: dict = {}


# ── Database helpers ──────────────────────────────────────────────────────────

def fetch_recent_articles(db_file: str, categories: list[str], hours: int = 24) -> list[dict]:
    """Fetch articles from the last `hours` hours, filtered by category."""
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        since = (datetime.now() - timedelta(hours=hours)).isoformat()

        if "all" in categories:
            rows = conn.execute("""
                SELECT title, link, summary, category, date, author
                FROM articles
                WHERE scraped_at >= ?
                ORDER BY id DESC
            """, (since,)).fetchall()
        else:
            placeholders = ",".join("?" * len(categories))
            rows = conn.execute(f"""
                SELECT title, link, summary, category, date, author
                FROM articles
                WHERE scraped_at >= ?
                AND category IN ({placeholders})
                ORDER BY id DESC
            """, [since] + categories).fetchall()

        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"DB error for {db_file}: {e}")
        return []


# ── Message formatting ────────────────────────────────────────────────────────

def format_digest(outlet: str, articles: list[dict], sent_links: set) -> tuple[str, set]:
    """
    Format articles into a readable Telegram message.
    Skips already-sent articles to avoid duplicates.
    Returns the message string and updated sent_links set.
    """
    new_articles = [a for a in articles if a["link"] not in sent_links]
    if not new_articles:
        return "", sent_links

    lines = [f"*{OUTLET_LABELS[outlet]}*\n"]
    for article in new_articles[:10]:  # max 10 per outlet per digest
        title = article["title"] or "No title"
        link  = article["link"] or ""
        cat   = article["category"] or ""
        lines.append(f"• [{title}]({link}) _{cat}_")
        sent_links.add(link)

    return "\n".join(lines), sent_links


# ── Job: send digest ──────────────────────────────────────────────────────────

async def send_digest(context: ContextTypes.DEFAULT_TYPE):
    """Called by the scheduler — sends digest to all users scheduled for this time."""
    current_hour = datetime.now().hour

    for chat_id, prefs in USER_PREFS.items():
        scheduled_hour = SEND_TIMES[prefs["time"]]["hour"]
        if current_hour != scheduled_hour:
            continue

        categories = prefs.get("categories", ["all"])
        outlets    = prefs.get("outlets", list(OUTLETS.keys()))
        sent_links = prefs.get("sent", set())

        messages_sent = 0
        for outlet in outlets:
            db_file  = OUTLETS[outlet]
            articles = fetch_recent_articles(db_file, categories)
            message, sent_links = format_digest(outlet, articles, sent_links)

            if message:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                    )
                    messages_sent += 1
                except Exception as e:
                    logger.error(f"Failed to send to {chat_id}: {e}")

        # Update sent links so we never send the same article twice
        USER_PREFS[chat_id]["sent"] = sent_links

        if messages_sent == 0:
            await context.bot.send_message(
                chat_id=chat_id,
                text="No new articles in the last 24 hours for your selected categories."
            )


# ── Command handlers ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message and setup prompt."""
    chat_id = update.effective_chat.id# type: ignore
    if chat_id not in USER_PREFS:
        USER_PREFS[chat_id] = {
            "time":       "9AM",
            "categories": ["all"],
            "outlets":    list(OUTLETS.keys()),
            "sent":       set(),
        }

    await update.message.reply_text( # type: ignore
        "👋 Welcome to *Nepal News Bot!*\n\n"
        "I'll send you daily news from eKantipur, Kathmandu Post, and Annapurna Post.\n\n"
        "Use these commands to customize:\n"
        "/time — Set your preferred delivery time\n"
        "/categories — Choose news categories\n"
        "/outlets — Choose news outlets\n"
        "/digest — Get news right now\n"
        "/settings — View your current settings\n"
        "/help — Show this message",
        parse_mode="Markdown"
    )


async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let user pick delivery time."""
    keyboard = [[
        InlineKeyboardButton("9 AM",  callback_data="time_9AM"),
        InlineKeyboardButton("12 PM", callback_data="time_12PM"),
        InlineKeyboardButton("6 PM",  callback_data="time_6PM"),
    ]]
    await update.message.reply_text(# type: ignore
        "🕐 When should I send your daily digest?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let user pick categories."""
    keyboard = []
    row = []
    for i, cat in enumerate(CATEGORIES):
        row.append(InlineKeyboardButton(cat.replace("_", " ").title(), callback_data=f"cat_{cat}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✅ Done", callback_data="cat_done")])

    chat_id = update.effective_chat.id# type: ignore
    current = USER_PREFS.get(chat_id, {}).get("categories", ["all"])
    await update.message.reply_text(# type: ignore
        f"📂 Choose categories (tap to toggle):\nCurrently: *{', '.join(current)}*\n\nTap a category to add/remove it, then tap Done.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def set_outlets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let user pick outlets."""
    keyboard = [[
        InlineKeyboardButton(label, callback_data=f"outlet_{key}")
        for key, label in OUTLET_LABELS.items()
    ]]
    keyboard.append([InlineKeyboardButton("✅ All Outlets", callback_data="outlet_all")])

    await update.message.reply_text(# type: ignore
        "📰 Which outlets do you want news from?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def get_digest_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send digest immediately on demand."""
    chat_id = update.effective_chat.id# type: ignore
    prefs = USER_PREFS.get(chat_id, {
        "categories": ["all"],
        "outlets": list(OUTLETS.keys()),
        "sent": set(),
    })

    await update.message.reply_text("⏳ Fetching latest news for you...")# type: ignore

    categories = prefs.get("categories", ["all"])
    outlets    = prefs.get("outlets", list(OUTLETS.keys()))
    sent_links = prefs.get("sent", set())
    found_any  = False

    for outlet in outlets:
        db_file  = OUTLETS[outlet]
        articles = fetch_recent_articles(db_file, categories)
        message, sent_links = format_digest(outlet, articles, sent_links)

        if message:
            found_any = True
            await update.message.reply_text(# type: ignore
                message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

    if chat_id in USER_PREFS:
        USER_PREFS[chat_id]["sent"] = sent_links

    if not found_any:
        await update.message.reply_text("No new articles found in the last 24 hours.")# type: ignore


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current user settings."""
    chat_id = update.effective_chat.id# type: ignore
    prefs = USER_PREFS.get(chat_id, {})

    time_val = prefs.get("time", "9AM")
    cats     = ", ".join(prefs.get("categories", ["all"]))
    outlets  = ", ".join([OUTLET_LABELS[o] for o in prefs.get("outlets", list(OUTLETS.keys()))])

    await update.message.reply_text(# type: ignore
        f"⚙️ *Your Settings*\n\n"
        f"🕐 Time: *{time_val}*\n"
        f"📂 Categories: *{cats}*\n"
        f"📰 Outlets: *{outlets}*",
        parse_mode="Markdown"
    )


# ── Callback handlers ─────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline keyboard button presses."""
    query   = update.callback_query
    chat_id = query.message.chat_id# type: ignore
    data    = query.data# type: ignore

    await query.answer()# type: ignore

    if chat_id not in USER_PREFS:
        USER_PREFS[chat_id] = {
            "time": "9AM", "categories": ["all"],
            "outlets": list(OUTLETS.keys()), "sent": set()
        }

    # ── Time selection ──
    if data.startswith("time_"):# type: ignore
        selected = data.replace("time_", "")# type: ignore
        USER_PREFS[chat_id]["time"] = selected
        await query.edit_message_text(f"✅ Delivery time set to *{selected}*", parse_mode="Markdown")# type: ignore

    # ── Category toggle ──
    elif data.startswith("cat_"):# type: ignore
        cat = data.replace("cat_", "")# type: ignore
        if cat == "done":
            current = USER_PREFS[chat_id]["categories"]
            await query.edit_message_text(# type: ignore
                f"✅ Categories saved: *{', '.join(current)}*", parse_mode="Markdown"
            )
        elif cat == "all":
            USER_PREFS[chat_id]["categories"] = ["all"]
            await query.edit_message_text("✅ Set to *all categories*", parse_mode="Markdown")# type: ignore
        else:
            current = USER_PREFS[chat_id]["categories"]
            if "all" in current:
                current = []
            if cat in current:
                current.remove(cat)
            else:
                current.append(cat)
            if not current:
                current = ["all"]
            USER_PREFS[chat_id]["categories"] = current
            await query.edit_message_text(# type: ignore
                f"📂 Selected: *{', '.join(current)}*\n\nTap more or press Done.",
                parse_mode="Markdown",
                reply_markup=query.message.reply_markup# type: ignore
            )

    # ── Outlet selection ──
    elif data.startswith("outlet_"):# type: ignore
        outlet = data.replace("outlet_", "")# type: ignore
        if outlet == "all":
            USER_PREFS[chat_id]["outlets"] = list(OUTLETS.keys())
            await query.edit_message_text("✅ Subscribed to *all outlets*", parse_mode="Markdown")# type: ignore
        else:
            current = USER_PREFS[chat_id]["outlets"]
            if outlet in current:
                current.remove(outlet)
            else:
                current.append(outlet)
            if not current:
                current = list(OUTLETS.keys())
            USER_PREFS[chat_id]["outlets"] = current
            labels = [OUTLET_LABELS[o] for o in current]
            await query.edit_message_text(# type: ignore
                f"✅ Outlets: *{', '.join(labels)}*", parse_mode="Markdown"
            )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("help",       start))
    app.add_handler(CommandHandler("time",       set_time))
    app.add_handler(CommandHandler("categories", set_categories))
    app.add_handler(CommandHandler("outlets",    set_outlets))
    app.add_handler(CommandHandler("digest",     get_digest_now))
    app.add_handler(CommandHandler("settings",   show_settings))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Schedule digest job—  runs every hour, checks if it's time to send
    app.job_queue.run_repeating(send_digest, interval=3600, first=10)# type: ignore

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()