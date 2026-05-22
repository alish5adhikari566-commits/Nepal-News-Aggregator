"""
database.py
------------
Handles all SQLite database operations for the eKantipur scraper.
Import this into your scraper and call the functions as needed.

Usage in Scraper.py:
    from database import init_db, save_article, print_preview, print_stats
"""

import json
import sqlite3
from datetime import datetime

DB_FILE = "Article.db"


def init_db(db_file: str = DB_FILE) -> sqlite3.Connection:
    """
    Creates the database and articles table if they don't exist.
    Call this ONCE at the start of your scraper before anything else.
    Returns a connection object — pass this to save_article().

    Example:
        conn = init_db()
    """
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA journal_mode=WAL")  # faster writes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            link        TEXT UNIQUE NOT NULL,
            summary     TEXT,
            date        TEXT,
            image       TEXT,
            body        TEXT,
            author      TEXT,
            tags        TEXT,
            category    TEXT NOT NULL,
            scraped_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    print(f"✓ Database ready: {db_file}")
    return conn


def save_article(conn: sqlite3.Connection, article: dict):
    """
    Saves a single article dict to the database.
    Skips duplicates silently via INSERT OR IGNORE on the link column.
    Call this for every article your scraper finds.

    Example:
        save_article(conn, {
            "title": "Some News",
            "link": "https://...",
            "summary": "...",
            "date": "...",
            "image": "...",
            "body": "",
            "author": "",
            "tags": [],
            "category": "politics",
        })
    """
    conn.execute("""
        INSERT OR IGNORE INTO articles
            (title, link, summary, date, image, body, author, tags, category, scraped_at)
        VALUES
            (:title, :link, :summary, :date, :image, :body, :author, :tags, :category, :scraped_at)
    """, {
        "title":      article.get("title", ""),
        "link":       article.get("link", ""),
        "summary":    article.get("summary", ""),
        "date":       article.get("date", ""),
        "image":      article.get("image", ""),
        "body":       article.get("body", ""),
        "author":     article.get("author", ""),
        "tags":       json.dumps(article.get("tags", []), ensure_ascii=False),
        "category":   article.get("category", ""),
        "scraped_at": datetime.now().isoformat(),
    })
    conn.commit()


def print_preview(db_file: str = DB_FILE, n: int = 5):
    """
    Prints the latest N articles from the database.
    Useful to quickly verify scraping worked.

    Example:
        print_preview(n=10)
    """
    conn = sqlite3.connect(db_file)
    rows = conn.execute(
        "SELECT category, title, link, date FROM articles ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()

    print("\n" + "=" * 55)
    print("  LATEST IN DB")
    print("=" * 55)
    for row in rows:
        print(f"\n  [{row[0].upper()}] {row[1]}")
        print(f"  {row[2]}")
        if row[3]:
            print(f"  {row[3]}")


def print_stats(db_file: str = DB_FILE):
    """
    Prints article count per category and total.
    Run anytime to see what's in your database.

    Example:
        print_stats()
    """
    conn = sqlite3.connect(db_file)
    rows = conn.execute(
        "SELECT category, COUNT(*) as count FROM articles GROUP BY category ORDER BY count DESC"
    ).fetchall()
    conn.close()

    print("\n" + "=" * 55)
    print("  DB STATS")
    print("=" * 55)
    total = 0
    for row in rows:
        print(f"  {row[0]:<20} {row[1]} articles")
        total += row[1]
    print(f"  {'TOTAL':<20} {total} articles")


    def test(Db=DB_FILE):
        conn = sqlite3.connect(db_file)
