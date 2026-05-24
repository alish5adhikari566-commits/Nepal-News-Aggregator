# 🇳🇵 Nepal News Aggregator

A multi-outlet Nepali news scraper with a Telegram bot that delivers daily digests straight to your phone.

Covers **eKantipur**, **Kathmandu Post**, and **Annapurna Post** — scraped, stored in SQLite, and delivered via Telegram on your schedule.

---

## Features

- Scrapes 3 major Nepali news outlets automatically
- Handles JS-rendered pages using Selenium with anti-detection
- Stores all articles in a local SQLite database with zero duplicates
- Telegram bot with daily digest delivery at 9AM, 12PM, or 6PM
- Users can filter by category — politics, sports, business, world, and more
- Duplicate article prevention across sessions

---

## Stack

| Layer | Tech |
|---|---|
| Scraping | Python, Selenium, BeautifulSoup4 |
| Anti-detection | fake-useragent, xvfb |
| Storage | SQLite |
| Bot | python-telegram-bot, APScheduler |
| Server | Ubuntu, Cron |

---

## Project Structure

```
news-tracker/
├── ekantipur_scraper.py     # eKantipur scraper
├── TheKathmanduPost.py      # Kathmandu Post scraper
├── Annapurna.py             # Annapurna Post scraper
├── database.py              # SQLite DB setup and helpers
├── bot.py                   # Telegram bot
├── Article.db               # eKantipur database
├── TheKtmPost.db            # Kathmandu Post database
└── AnnapurnaArticle.db      # Annapurna database
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/alish5adhikari566-commits/News-Tracker.git
cd News-Tracker
```

### 2. Install dependencies

```bash
pip install selenium beautifulsoup4 webdriver-manager fake-useragent python-telegram-bot apscheduler
```

### 3. Install Chrome

```bash
# Ubuntu
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

### 4. Install virtual display (for headless server)

```bash
sudo apt install xvfb
```

### 5. Set your Telegram bot token

Open `bot.py` and replace:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
```
Get a token from [@BotFather](https://t.me/botfather) on Telegram.

---

## Running the scrapers

```bash
# Run all scrapers manually
python ekantipur_scraper.py --no-headless
python TheKathmanduPost.py --no-headless
python Annapurna.py --no-headless

# Scrape specific categories only
python ekantipur_scraper.py --no-headless --categories politics sports

# Scrape multiple pages per category
python ekantipur_scraper.py --no-headless --pages 3

# Also scrape full article body text
python ekantipur_scraper.py --no-headless --full
```

---

## Running the bot

```bash
python bot.py
```

### Bot commands

| Command | Description |
|---|---|
| `/start` | Welcome and setup |
| `/time` | Set delivery time (9AM, 12PM, 6PM) |
| `/categories` | Choose news categories |
| `/outlets` | Choose which outlets to follow |
| `/digest` | Get news right now |
| `/settings` | View your current preferences |

---

## Scheduling on Ubuntu server

Run scrapers daily at 3AM so the database is fresh before the 9AM digest:

```bash
crontab -e
```

Add:
```
0 3 * * * cd /home/user/News-Tracker && xvfb-run python3 ekantipur_scraper.py --no-headless
0 3 * * * cd /home/user/News-Tracker && xvfb-run python3 TheKathmanduPost.py --no-headless
0 3 * * * cd /home/user/News-Tracker && xvfb-run python3 Annapurna.py --no-headless
```

Keep the bot running permanently with systemd:

```bash
sudo nano /etc/systemd/system/newsbot.service
```

```
[Unit]
Description=Nepal News Bot

[Service]
WorkingDirectory=/home/user/News-Tracker
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable newsbot
sudo systemctl start newsbot
```

---

## Database

Check what's in your database anytime:

```bash
python ekantipur_scraper.py --stats
```

Each article is stored with:

| Field | Description |
|---|---|
| title | Article headline |
| link | Full URL (unique) |
| summary | Short description |
| date | Publication date |
| image | Thumbnail URL |
| body | Full article text (if --full used) |
| author | Author name |
| tags | Article tags (JSON array) |
| category | News category |
| scraped_at | Timestamp of when it was scraped |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `database is locked` | Close DB Browser for SQLite before running |
| `0 articles found` | CSS selectors may need updating — inspect site HTML |
| `Connection reset error` | Run with `--no-headless` flag |
| `KeyboardInterrupt` on startup | Use `--no-headless`, headless mode gets detected |
| ChromeDriver mismatch | `pip install --upgrade webdriver-manager` |

---

## Roadmap

- [ ] English translation of Nepali articles
- [ ] Keyword alerts
- [ ] Persist user preferences to database
- [ ] Web dashboard
- [ ] More outlets

---

## Disclaimer

This project is for personal and educational use only. Scraping may conflict with the terms of service of the websites involved. Use responsibly.
