#Dependiences
import time
import random
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from database import init_db, save_article, print_stats # type: ignore 

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WDM = True
except ImportError:
    USE_WDM = False

try:
    from fake_useragent import UserAgent
    ua = UserAgent()
    def get_ua(): # type: ignore
        return ua.chrome  
except ImportError:
    def get_ua():
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )


# ── Config ───────────────────────────────────────────────────────────────────

BASE_URL = "https://kathmandupost.com"

CATEGORIES = {
    "politics":      "/politics",
    "opinion":       "/opinion",
    "National":     "/national",
    "Valley":       "/valley",
    "Money":        "/money",
    "sports":       "/sports",
    "Culture":      "/art-culture"
}


def human_delay(min_s=3.0, max_s=7.0): # Makes st so that a random second from 3-7 in selected so that the bot detection is harder
    time.sleep(random.uniform(min_s, max_s))


# ── Driver setup ─────────────────────────────────────────────────────────────

def make_driver(headless: bool = True) -> webdriver.Chrome:#settinh up the Browser enviroment
    opts = Options()
    if USE_WDM:
        service = Service(ChromeDriverManager().install()) # type: ignore
        driver = webdriver.Chrome(service=service, options=opts)
    else:
        driver = webdriver.Chrome(options=opts)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    return driver


def rotate_ua(driver):#Randomly choses a fake user agent from an imported library 
    new_ua = get_ua()
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": new_ua})
    print(f"  ↻ Rotated UA: {new_ua[:60]}...")


# ── Page helpers ─────────────────────────────────────────────────────────────

def get_page(driver, url: str, wait_selector: str = "body", timeout: int = 20): #Makes it so that the scraping is done After some element is loaded 
    driver.get(url)
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
        )
    except Exception:
        human_delay(1, 2)


def human_scroll(driver):#Scrolls down the page in random small steps (200–600px) with random pauses between each step.
    total_height = driver.execute_script("return document.body.scrollHeight")
    current = 0
    while current < total_height:
        step = random.randint(200, 600)
        current = min(current + step, total_height)
        driver.execute_script(f"window.scrollTo(0, {current});")
        time.sleep(random.uniform(0.3, 0.9))
    driver.execute_script(f"window.scrollTo(0, {total_height // 2});")
    time.sleep(random.uniform(0.5, 1.2))


def get_soup(driver) -> BeautifulSoup:#Setsup Beautiful soup fot parsing scraped data
    return BeautifulSoup(driver.page_source, "html.parser")


# ── Parsers ──────────────────────────────────────────────────────────────────

def parse_listing(soup: BeautifulSoup, category: str) -> list[dict]:# The main scraper, It searches for all the provided CSS selectors and parses the data in them.Returns tbe storable data
    articles = []

    cards = (
        soup.select(".article-image ") 
    )

    print(f"    Raw cards found: {len(cards)}")

    for card in cards:
        a_tag = card.select_one("a[href]")
        if not a_tag:
            continue

        link = str(a_tag.get("href", ""))
        if not link:
            continue
        if not link.startswith("http"):
            link = BASE_URL + link

        title_tag = card.select_one("h3")
        title = title_tag.get_text(strip=True) if title_tag else a_tag.get_text(strip=True)
        if not title:
            continue

        summary_tag = card.select_one("p")
        summary = summary_tag.get_text(strip=True) if summary_tag else ""


        articles.append({
            "title":    title,
            "link":     link,
            "summary":  summary,
            "category": category,
        })

    return articles


def parse_article(soup: BeautifulSoup) -> dict:
    body_tag = (
        soup.select_one("div.article-body") or
        soup.select_one("div.story-content") or
        soup.select_one("div.content-detail") or
        soup.select_one("div.post-content") or
        soup.select_one("article .body") or
        soup.select_one("div[class*='content']")
    )
    body = ""
    if body_tag:
        for junk in body_tag.select("script, style, .advertisement, .ad, .related"):
            junk.decompose()
        body = body_tag.get_text(separator="\n", strip=True)

    author_tag = soup.select_one(".author, .byline, [rel='author'], .reporter")
    author = author_tag.get_text(strip=True) if author_tag else ""
    tags = [t.get_text(strip=True) for t in soup.select(".tags a, .tag-list a, .keywords a")]

    return {"body": body, "author": author, "tags": tags}


# ── Main ─────────────────────────────────────────────────────────────────────

def scrape(
    categories: dict = CATEGORIES,
    full_articles: bool = False,
    pages: int = 1,
    headless: bool = False,
) -> list[dict]: # The main function thar calls all the above functions and runs the scraper
   
    conn=init_db("TheKtmPostArticle.db") #initializing database
    print("=" * 55)
    print("  TheKTM Post Scraper Selenium Scraper")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  headless={headless}  full_articles={full_articles}  pages={pages}")
    print("=" * 55)

    driver = make_driver(headless=headless)
    all_articles = []
    seen = set()

    try:
        print("\n  Visiting homepage first...")
        get_page(driver, BASE_URL)
        human_delay(3, 6)

        for i, (cat, path) in enumerate(categories.items()):
            print(f"\n── {cat.upper()} ──")

            # Rotate UA between every category
            rotate_ua(driver)

            for page in range(1, pages + 1):
                url = f"{BASE_URL}{path}"
                if page > 1:
                    url += f"?page={page}"

                print(f"  Loading: {url}")
                get_page(driver, url)
                human_scroll(driver)

                soup = get_soup(driver)
                stubs = parse_listing(soup, cat)
                print(f"  Parsed {len(stubs)} articles")

                for stub in stubs:
                    if stub["link"] in seen:
                        continue
                    seen.add(stub["link"])

                    if full_articles and stub["link"]:
                        print(f"    → {stub['title'][:60]}")
                        get_page(driver, stub["link"])
                        human_scroll(driver)
                        detail = parse_article(get_soup(driver))
                        stub.update(detail)
                        human_delay(3, 6)

                    save_article(conn,stub)

                human_delay()

    finally:
        conn.close()
        driver.quit()

    print(f"\n✓ Total unique articles: {len(all_articles)}")

    return all_articles


def print_preview(articles: list[dict], n: int = 3):#Just prints a sample of scraped articles to the terminal so you can quickly check if it worked without opening the JSON file.
    from collections import defaultdict
    by_cat = defaultdict(list)
    for a in articles:
        by_cat[a["category"]].append(a)

    print("\n" + "=" * 55)
    print("  PREVIEW")
    print("=" * 55)
    for cat, items in by_cat.items():
        print(f"\n── {cat.upper()} ({len(items)} total) ──")
        for item in items[:n]:
            print(f"  {item['title']}")
            print(f"  {item['link']}")
            if item.get("date"):
                print(f"  {item['date']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape eKantipur with Selenium")
    parser.add_argument("--categories", nargs="+", choices=list(CATEGORIES.keys()),
                        help="Categories to scrape (default: all)")
    parser.add_argument("--pages", type=int, default=1,
                        help="Listing pages per category (default: 1)")
    parser.add_argument("--full", action="store_true",
                        help="Also scrape full article body (slow)")
    parser.add_argument("--output", default="KathmanduPost.json",
                        help="Output JSON file")
    parser.add_argument("--no-headless", action="store_true",
                        help="Show browser window (good for debugging)")
    parser.add_argument("--preview", type=int, default=3)
    args = parser.parse_args()

    cats = {k: CATEGORIES[k] for k in args.categories} if args.categories else CATEGORIES

    articles = scrape(
        categories=cats,
        full_articles=args.full,
        pages=args.pages,
        headless=not args.no_headless,
    )
    print_stats()

    #python TheKathmanduPost.py --no-headless