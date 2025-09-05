"""Core news scraping and Reddit posting manager.

Refactored from legacy feed_scraper.py monolith. Responsibilities:
 - Data persistence (SQLite)
 - Source scraping orchestration
 - Reddit posting

Future enhancements: retries, metrics, structured logging, async.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import praw
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dt_parser
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH")  # if unset we resolve below

def _build_reddit_config():  # copied unchanged for now
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    refresh_token = os.getenv("REDDIT_REFRESH_TOKEN")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")

    missing = [k for k, v in {
        "REDDIT_CLIENT_ID": client_id,
        "REDDIT_CLIENT_SECRET": client_secret,
        "REDDIT_USER_AGENT": user_agent,
    }.items() if not v]
    if missing:
        raise RuntimeError(
            "Reddit credentials missing: " + ", ".join(missing) +
            ". Set them in your environment or .env."
        )

    config: dict[str, str] = {
        "client_id": client_id,  # type: ignore[arg-type]
        "client_secret": client_secret,  # type: ignore[arg-type]
        "user_agent": user_agent,  # type: ignore[arg-type]
    }
    if refresh_token:
        config["refresh_token"] = refresh_token
    else:
        if not username or not password:
            raise RuntimeError(
                "Reddit credentials incomplete: provide REDDIT_REFRESH_TOKEN or both REDDIT_USERNAME and REDDIT_PASSWORD."
            )
        config["username"] = username
        config["password"] = password
    return config


RSS_FEEDS = {
    "wuky": "https://www.wuky.org/local-regional-news.rss",
    "weku": "https://www.weku.org/lexington-richmond.rss",
    "fox56": "https://fox56news.com/feed/",
    "wtvq": "https://www.wtvq.com/category/local-news/feed/",
    "lex18": "https://www.lex18.com/news/covering-kentucky.rss",
    "kykernel": "https://kykernel.com/category/news-campus/feed",
    "lextoday": "https://lextoday.6amcity.com/index.rss",
    "lexingtontimes": "https://lexingtonky.news/feed/",
    "kyweathercenter": "https://kyweathercenter.com/?feed=rss2",
}

FLAIR_IDS = {
    "general": os.getenv("FLAIR_ID_GENERAL"),
    "fire": os.getenv("FLAIR_ID_FIRE"),
    "homeless": os.getenv("FLAIR_ID_HOMELESS"),
}

BLOCKED_SOURCES = {s.strip().lower() for s in (os.getenv("REDDIT_BLOCKED_SOURCES", "").split(",") or []) if s.strip()}
BLOCKED_DOMAINS = {s.strip().lower() for s in (os.getenv("REDDIT_BLOCKED_DOMAINS", "").split(",") or []) if s.strip()}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class NewsManager:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(__file__))  # project root
        if DB_PATH:
            self.db_path = DB_PATH if os.path.isabs(DB_PATH) else os.path.abspath(os.path.join(base_dir, DB_PATH))
        else:
            legacy = os.path.abspath(os.path.join(base_dir, "rss_feed_data.db"))
            database_dir = os.path.abspath(os.path.join(base_dir, "database"))
            os.makedirs(database_dir, exist_ok=True)
            preferred = os.path.join(database_dir, "rss_feed_data.db")
            self.db_path = legacy if os.path.exists(legacy) else preferred
        self.reddit = None
        self.create_database()

    # --- utility / infra ---
    @staticmethod
    def _sanitize_title(text: str) -> str:
        replacements = {
            "\u2018": "'", "\u2019": "'", "\u201C": '"', "\u201D": '"',
            "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00A0": " ",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        return text

    def create_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rss_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT UNIQUE,
                    source TEXT,
                    url TEXT,
                    headline TEXT,
                    summary TEXT,
                    published TEXT,
                    posted INTEGER DEFAULT 0
                )
                """
            )

    def generate_hash(self, entry):
        unique_string = entry["url"] + entry["headline"] + entry["published"]
        return hashlib.sha256(unique_string.encode("utf-8")).hexdigest()

    # --- scraping functions --- (copied mostly verbatim for now)
    def scrape_rss_feeds(self):
        print("📰 Starting RSS feed scraping...")
        new_articles = 0
        for source, url in RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                logging.info(f"Processing {source}: {len(feed.entries)} entries")
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    for entry in feed.entries:
                        try:
                            headline = entry.title
                            article_url = entry.link
                            summary = getattr(entry, "summary", "")
                            published = entry.published if hasattr(entry, "published") else datetime.now().isoformat()
                            try:
                                published_dt = dt_parser.parse(published)
                                published = published_dt.isoformat()
                            except:  # noqa: E722
                                published = datetime.now().isoformat()
                            entry_data = {"url": article_url, "headline": headline, "published": published}
                            entry_hash = self.generate_hash(entry_data)
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (entry_hash, source, article_url, headline, summary, published),
                            )
                            if cursor.rowcount > 0:
                                new_articles += 1
                        except Exception as e:  # noqa: BLE001
                            logging.error(f"Error processing entry from {source}: {e}")
            except Exception as e:  # noqa: BLE001
                logging.error(f"Error processing feed {source}: {e}")
        print(f"✅ RSS scraping completed. Added {new_articles} new articles")
        return new_articles

    def scrape_wkyt_news(self):  # ... unchanged logic
        try:
            url = "https://www.wkyt.com/news/local/"
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for article in soup.find_all("a", class_="story-link"):
                    try:
                        headline = article.get_text(strip=True)
                        if headline and len(headline) > 10:
                            article_url = urljoin(url, article["href"])
                            published = datetime.now().isoformat()
                            entry_data = {"url": article_url, "headline": headline, "published": published}
                            entry_hash = self.generate_hash(entry_data)
                            cursor.execute(
                                """INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                                (entry_hash, "wkyt", article_url, headline, "", published),
                            )
                            if cursor.rowcount > 0:
                                new_articles += 1
                    except Exception as e:  # noqa: BLE001
                        logging.error(f"Error processing WKYT article: {e}")
            print(f"✅ WKYT scraping completed. Added {new_articles} new articles")
            return new_articles
        except Exception as e:  # noqa: BLE001
            logging.error(f"Error scraping WKYT news: {e}")
            return 0

    def scrape_wkyt_good_questions(self):
        try:
            base_url = "https://www.wkyt.com/news/good-question/"
            response = requests.get(base_url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                span_elements = soup.find_all("span", style=lambda v: v and "textDecoration: none" in v)
                for span in span_elements:
                    try:
                        a_tag = span.find_parent("a")
                        if a_tag and "href" in a_tag.attrs:
                            article_url = urljoin(base_url, a_tag["href"])
                            page_response = requests.get(article_url, timeout=10)
                            page_soup = BeautifulSoup(page_response.text, "html.parser")
                            h1_tag = page_soup.find("h1")
                            if h1_tag:
                                headline = h1_tag.get_text(strip=True)
                                published = datetime.now().isoformat()
                                entry_data = {"url": article_url, "headline": headline, "published": published}
                                entry_hash = self.generate_hash(entry_data)
                                cursor.execute(
                                    """INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                    VALUES (?, ?, ?, ?, ?, ?)""",
                                    (entry_hash, "wkyt_questions", article_url, headline, "", published),
                                )
                                if cursor.rowcount > 0:
                                    new_articles += 1
                    except Exception as e:  # noqa: BLE001
                        logging.error(f"Error processing WKYT Good Question article: {e}")
            print(f"✅ WKYT Good Questions scraping completed. Added {new_articles} new articles")
            return new_articles
        except Exception as e:  # noqa: BLE001
            logging.error(f"Error scraping WKYT Good Questions: {e}")
            return 0

    def scrape_newsapi(self):
        try:
            api_key = os.getenv("NEWSAPI_ORG_KEY")
            if not api_key:
                print("⚠️ NEWSAPI_ORG_KEY not found in environment variables")
                return 0
            url = "https://newsapi.org/v2/everything"
            today = datetime.now()
            one_week_ago = today - timedelta(days=7)
            params = {
                "q": "Lexington Kentucky",
                "from": one_week_ago.strftime("%Y-%m-%d"),
                "to": today.strftime("%Y-%m-%d"),
                "apiKey": api_key,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": 20,
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for article in data.get("articles", []):
                    try:
                        headline = article.get("title", "")
                        article_url = article.get("url", "")
                        summary = article.get("description", "")
                        published = article.get("publishedAt", datetime.now().isoformat())
                        source_name = article.get("source", {}).get("name", "NewsAPI")
                        if headline and article_url:
                            entry_data = {"url": article_url, "headline": headline, "published": published}
                            entry_hash = self.generate_hash(entry_data)
                            cursor.execute(
                                """INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                                (entry_hash, f"newsapi_{source_name}", article_url, headline, summary, published),
                            )
                            if cursor.rowcount > 0:
                                new_articles += 1
                    except Exception as e:  # noqa: BLE001
                        logging.error(f"Error processing NewsAPI article: {e}")
            print(f"✅ NewsAPI scraping completed. Added {new_articles} new articles")
            return new_articles
        except Exception as e:  # noqa: BLE001
            logging.error(f"Error scraping NewsAPI: {e}")
            return 0

    def scrape_civiclex_news(self):
        try:
            base_url = "https://civiclex.org/news"
            response = requests.get(base_url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for article in soup.find_all("a", href=True):
                    try:
                        headline = article.get_text(strip=True)
                        if headline and len(headline) > 10 and "/news/" in article["href"]:
                            article_url = urljoin(base_url, article["href"])
                            published = datetime.now().isoformat()
                            entry_data = {"url": article_url, "headline": headline, "published": published}
                            entry_hash = self.generate_hash(entry_data)
                            cursor.execute(
                                """INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                                (entry_hash, "civiclex", article_url, headline, "", published),
                            )
                            if cursor.rowcount > 0:
                                new_articles += 1
                    except Exception as e:  # noqa: BLE001
                        logging.error(f"Error processing CivicLex article: {e}")
            print(f"✅ CivicLex scraping completed. Added {new_articles} new articles")
            return new_articles
        except Exception as e:  # noqa: BLE001
            logging.error(f"Error scraping CivicLex news: {e}")
            return 0

    def scrape_central_bank_center(self):
        try:
            url = "https://www.centralbankcenter.com/news"
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for div in soup.find_all("div", class_="info"):
                    try:
                        date_span = div.find("span", class_="m-date__singleDate")
                        date_text = date_span.get_text(strip=True) if date_span else ""
                        a_tag = div.find("a", href=True)
                        if a_tag:
                            headline = a_tag.get_text(strip=True)
                            article_url = urljoin(url, a_tag["href"])
                            published = datetime.now().isoformat()
                            if headline and len(headline) > 5:
                                entry_data = {"url": article_url, "headline": headline, "published": published}
                                entry_hash = self.generate_hash(entry_data)
                                cursor.execute(
                                    """INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                    VALUES (?, ?, ?, ?, ?, ?)""",
                                    (entry_hash, "central_bank", article_url, headline, date_text, published),
                                )
                                if cursor.rowcount > 0:
                                    new_articles += 1
                    except Exception as e:  # noqa: BLE001
                        logging.error(f"Error processing Central Bank Center article: {e}")
            print(f"✅ Central Bank Center scraping completed. Added {new_articles} new articles")
            return new_articles
        except Exception as e:  # noqa: BLE001
            logging.error(f"Error scraping Central Bank Center: {e}")
            return 0

    def clean_lexgov_headline(self, headline):
        import re
        pattern = r"^\w{3,4} \d{1,2}, \d{4} \d{1,2}:\d{2} [ap]\.m\.\s*"
        return re.sub(pattern, "", headline).strip()

    def scrape_lexington_gov_news(self):
        try:
            url = "https://www.lexingtonky.gov/news"
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                news_items = soup.find_all("div", class_="row")
                for item in news_items[:10]:
                    try:
                        url_tag = item.find("a")
                        date = item.find("time")
                        description_tag = item.find("div", class_="description")
                        if url_tag and date and description_tag:
                            href = url_tag["href"]
                            headline = url_tag.get_text(strip=True)
                            cleaned_headline = self.clean_lexgov_headline(headline)
                            published = date.get("datetime", date.get_text(strip=True))
                            summary = description_tag.get_text(strip=True)
                            full_url = ("https://www.lexingtonky.gov" + href) if href.startswith("/") else href
                            if cleaned_headline and len(cleaned_headline) > 5:
                                entry_data = {"url": full_url, "headline": cleaned_headline, "published": published}
                                entry_hash = self.generate_hash(entry_data)
                                cursor.execute(
                                    """INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                    VALUES (?, ?, ?, ?, ?, ?)""",
                                    (entry_hash, "lexington_gov", full_url, cleaned_headline, summary, published),
                                )
                                if cursor.rowcount > 0:
                                    new_articles += 1
                    except Exception as e:  # noqa: BLE001
                        logging.error(f"Error processing Lexington Government article: {e}")
            print(f"✅ Lexington Government scraping completed. Added {new_articles} new articles")
            return new_articles
        except Exception as e:  # noqa: BLE001
            logging.error(f"Error scraping Lexington Government news: {e}")
            return 0

    def scrape_newsdata_apis(self):
        total_new = 0
        newsdata_key = os.getenv("NEWSDATA_API_KEY")
        if newsdata_key:
            total_new += self.scrape_newsdata_io(newsdata_key)
        else:
            print("⚠️ NEWSDATA_API_KEY not found - skipping NewsData.io")
        mediastack_key = os.getenv("MEDIASTACK_API_KEY")
        if mediastack_key:
            total_new += self.scrape_mediastack(mediastack_key)
        else:
            print("⚠️ MEDIASTACK_API_KEY not found - skipping MediaStack")
        return total_new

    def scrape_newsdata_io(self, api_key):
        try:
            url = "https://newsdata.io/api/1/news"
            params = {"apikey": api_key, "q": "Lexington Kentucky", "country": "us", "language": "en", "size": 10}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            if data.get("status") != "success":
                print(f"⚠️ NewsData.io API error: {data.get('message', 'Unknown error')}")
                return 0
            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for article in data.get("results", []):
                    try:
                        title = article.get("title", "")
                        link = article.get("link", "")
                        description = article.get("description", "")
                        pub_date = article.get("pubDate", datetime.now().isoformat())
                        if title and link and len(title) > 5:
                            entry_data = {"url": link, "headline": title, "published": pub_date}
                            entry_hash = self.generate_hash(entry_data)
                            cursor.execute(
                                """INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                                (entry_hash, "newsdata_io", link, title, description, pub_date),
                            )
                            if cursor.rowcount > 0:
                                new_articles += 1
                    except Exception as e:  # noqa: BLE001
                        logging.error(f"Error processing NewsData.io article: {e}")
            print(f"✅ NewsData.io scraping completed. Added {new_articles} new articles")
            return new_articles
        except Exception as e:  # noqa: BLE001
            logging.error(f"Error scraping NewsData.io: {e}")
            return 0

    def scrape_mediastack(self, api_key):
        try:
            url = "http://api.mediastack.com/v1/news"
            params = {"access_key": api_key, "keywords": "Lexington Kentucky", "countries": "us", "languages": "en", "limit": 10}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            if "error" in data:
                print(f"⚠️ MediaStack API error: {data['error'].get('info', 'Unknown error')}")
                return 0
            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for article in data.get("data", []):
                    try:
                        title = article.get("title", "")
                        url_link = article.get("url", "")
                        description = article.get("description", "")
                        pub_date = article.get("published_at", datetime.now().isoformat())
                        if title and url_link and len(title) > 5:
                            entry_data = {"url": url_link, "headline": title, "published": pub_date}
                            entry_hash = self.generate_hash(entry_data)
                            cursor.execute(
                                """INSERT OR IGNORE INTO rss_data (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                                (entry_hash, "mediastack", url_link, title, description, pub_date),
                            )
                            if cursor.rowcount > 0:
                                new_articles += 1
                    except Exception as e:  # noqa: BLE001
                        logging.error(f"Error processing MediaStack article: {e}")
            print(f"✅ MediaStack scraping completed. Added {new_articles} new articles")
            return new_articles
        except Exception as e:  # noqa: BLE001
            logging.error(f"Error scraping MediaStack: {e}")
            return 0

    # --- reddit posting ---
    def get_flair_id(self, headline):
        headline_lower = headline.lower()
        if any(word in headline_lower for word in ["shot", "shots", "shooter", "shooters", "shooting", "gunshot", "gunshots"]):
            return FLAIR_IDS["general"]
        if "fire" in headline_lower:
            return FLAIR_IDS["fire"]
        if any(word in headline_lower for word in ["homeless", "homelessness", "unhoused"]):
            return FLAIR_IDS["homeless"]
        return None

    def init_reddit(self):
        if not self.reddit:
            config = _build_reddit_config()
            self.reddit = praw.Reddit(**config)
        return self.reddit

    def fetch_unposted_articles(self, limit: Optional[int] = None, source: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            params = []
            where = ["posted = 0"]
            if source:
                where.append("source = ?")
                params.append(source)
            sql = "SELECT id, url, headline, source, published FROM rss_data WHERE " + " AND ".join(where) + " ORDER BY published DESC, id DESC"
            if limit:
                sql += " LIMIT ?"
                params.append(limit)
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            if BLOCKED_SOURCES or BLOCKED_DOMAINS:
                filtered = []
                for r_id, r_url, r_headline, r_source, r_published in rows:
                    if r_source and r_source.lower() in BLOCKED_SOURCES:
                        continue
                    try:
                        host = urlparse(r_url).netloc.lower()
                    except Exception:  # noqa: BLE001
                        host = ""
                    if host and any(host.endswith(d) or host == d for d in BLOCKED_DOMAINS):
                        continue
                    filtered.append((r_id, r_url, r_headline, r_source, r_published))
                rows = filtered
            return rows

    def post_to_reddit(self, post_id, url, headline, source):
        try:
            reddit = self.init_reddit()
            subreddit = reddit.subreddit(os.getenv("SUBREDDIT_NAME", "newsoflexingtonky"))
            title = f"[{source.upper()}] {headline}"
            title = self._sanitize_title(title)
            if len(title) > 300:
                title = title[:297] + "..."
            submission = subreddit.submit(title=title, url=url)
            flair_id = self.get_flair_id(headline)
            if flair_id:
                try:
                    submission.flair.select(flair_id)
                except Exception:  # noqa: BLE001
                    pass
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE rss_data SET posted = 1 WHERE id = ?", (post_id,))
            logging.info(f"✅ Posted to Reddit: {headline[:50]}...")
            return True
        except Exception as e:  # noqa: BLE001
            logging.error(f"❌ Failed to post {headline[:50]}...: {e}")
            return False

    def post_unposted_articles(self, limit: int = 5, source: Optional[str] = None):
        unposted = self.fetch_unposted_articles(limit=limit, source=source)
        posted_count = 0
        if not unposted:
            print("📰 No unposted articles found")
            return 0
        print(f"📰 Posting {len(unposted)} articles to Reddit...")
        for post_id, url, headline, source, published in unposted:
            print(f"📅 Posting: [{source.upper()}] {headline[:50]}... (Published: {published[:16]})")
            if source and source.lower() in BLOCKED_SOURCES:
                print(f"⏭️  Skipping banned source: {source}")
                continue
            try:
                host = urlparse(url).netloc.lower()
            except Exception:  # noqa: BLE001
                host = ""
            if host and any(host.endswith(d) or host == d for d in BLOCKED_DOMAINS):
                print(f"⏭️  Skipping banned domain: {host}")
                continue
            if self.post_to_reddit(post_id, url, headline, source):
                posted_count += 1
                time.sleep(2)
        print(f"✅ Posted {posted_count}/{len(unposted)} articles to Reddit")
        return posted_count

    # --- orchestration ---
    def scrape_all(self):
        total_new = 0
        total_new += self.scrape_rss_feeds()
        total_new += self.scrape_lexington_gov_news()
        total_new += self.scrape_wkyt_news()
        total_new += self.scrape_wkyt_good_questions()
        total_new += self.scrape_newsapi()
        total_new += self.scrape_civiclex_news()
        total_new += self.scrape_central_bank_center()
        total_new += self.scrape_newsdata_apis()
        return total_new

__all__ = ["NewsManager"]
