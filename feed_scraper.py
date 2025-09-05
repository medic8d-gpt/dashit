#!/usr/bin/env python3
"""
News Scraper and Reddit Poster
Consolidates RSS feed collection, news site scraping, and Reddit posting functionality
"""
import feedparser
import sqlite3
import hashlib
from datetime import datetime, timedelta
import dateutil.parser as parser
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import praw
import logging
import os
import argparse
import time
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database path (from environment or default project-root file)
# If `DB_PATH` is relative, resolve relative to this repository root.
DB_PATH = os.getenv("DB_PATH", "rss_feed_data.db")

# Reddit API credentials from environment variables
REDDIT_CONFIG = {
    "client_id": os.getenv("REDDIT_CLIENT_ID"),
    "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
    "user_agent": os.getenv("REDDIT_USER_AGENT"),
    "username": os.getenv("REDDIT_USERNAME"),
    "password": os.getenv("REDDIT_PASSWORD"),
}

# RSS Feeds
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

# Flair IDs for Reddit posts (from environment variables)
FLAIR_IDS = {
    "general": os.getenv("FLAIR_ID_GENERAL"),
    "fire": os.getenv("FLAIR_ID_FIRE"),
    "homeless": os.getenv("FLAIR_ID_HOMELESS"),
}

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class NewsManager:
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        # Absolute if provided; else resolve relative to the project root
        self.db_path = (
            DB_PATH if os.path.isabs(DB_PATH) else os.path.abspath(os.path.join(base_dir, DB_PATH))
        )
        self.reddit = None
        self.create_database()

    def create_database(self):
        """Create the database and table if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
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
            conn.commit()

    def generate_hash(self, entry):
        """Generate a hash for a feed entry to ensure uniqueness"""
        unique_string = entry["url"] + entry["headline"] + entry["published"]
        return hashlib.sha256(unique_string.encode("utf-8")).hexdigest()

    def scrape_rss_feeds(self):
        """Scrape all RSS feeds and store in database"""
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
                            # Parse entry data
                            headline = entry.title
                            article_url = entry.link
                            summary = getattr(entry, "summary", "")
                            published = (
                                entry.published
                                if hasattr(entry, "published")
                                else datetime.now().isoformat()
                            )

                            # Normalize published date
                            try:
                                published_dt = parser.parse(published)
                                published = published_dt.isoformat()
                            except:
                                published = datetime.now().isoformat()

                            # Create entry dict for hashing
                            entry_data = {
                                "url": article_url,
                                "headline": headline,
                                "published": published,
                            }

                            entry_hash = self.generate_hash(entry_data)

                            # Insert into database
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO rss_data
                                (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    entry_hash,
                                    source,
                                    article_url,
                                    headline,
                                    summary,
                                    published,
                                ),
                            )

                            if cursor.rowcount > 0:
                                new_articles += 1

                        except Exception as e:
                            logging.error(f"Error processing entry from {source}: {e}")

                    conn.commit()

            except Exception as e:
                logging.error(f"Error processing feed {source}: {e}")

        print(f"✅ RSS scraping completed. Added {new_articles} new articles")
        return new_articles

    def scrape_wkyt_news(self):
        """Scrape WKYT news site"""
        try:
            url = "https://www.wkyt.com/news/local/"
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")

            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Find news articles
                articles = soup.find_all("a", class_="story-link")
                for article in articles:
                    try:
                        headline = article.get_text(strip=True)
                        if headline and len(headline) > 10:
                            article_url = urljoin(url, article["href"])
                            published = datetime.now().isoformat()

                            entry_data = {
                                "url": article_url,
                                "headline": headline,
                                "published": published,
                            }

                            entry_hash = self.generate_hash(entry_data)

                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO rss_data
                                (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    entry_hash,
                                    "wkyt",
                                    article_url,
                                    headline,
                                    "",
                                    published,
                                ),
                            )

                            if cursor.rowcount > 0:
                                new_articles += 1
                    except Exception as e:
                        logging.error(f"Error processing WKYT article: {e}")

                conn.commit()

            print(f"✅ WKYT scraping completed. Added {new_articles} new articles")
            return new_articles

        except Exception as e:
            logging.error(f"Error scraping WKYT news: {e}")
            return 0

    def scrape_wkyt_good_questions(self):
        """Scrape WKYT Good Question section"""
        try:
            base_url = "https://www.wkyt.com/news/good-question/"
            response = requests.get(base_url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Find all span elements with specific style
                span_elements = soup.find_all(
                    "span",
                    style=lambda value: value and "textDecoration: none" in value,
                )

                for span in span_elements:
                    try:
                        a_tag = span.find_parent("a")
                        if a_tag and "href" in a_tag.attrs:
                            article_url = urljoin(base_url, a_tag["href"])

                            # Fetch individual article
                            page_response = requests.get(article_url, timeout=10)
                            page_soup = BeautifulSoup(page_response.text, "html.parser")

                            # Get headline from h1
                            h1_tag = page_soup.find("h1")
                            if h1_tag:
                                headline = h1_tag.get_text(strip=True)
                                published = datetime.now().isoformat()

                                entry_data = {
                                    "url": article_url,
                                    "headline": headline,
                                    "published": published,
                                }

                                entry_hash = self.generate_hash(entry_data)

                                cursor.execute(
                                    """
                                    INSERT OR IGNORE INTO rss_data
                                    (hash, source, url, headline, summary, published)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                    (
                                        entry_hash,
                                        "wkyt_questions",
                                        article_url,
                                        headline,
                                        "",
                                        published,
                                    ),
                                )

                                if cursor.rowcount > 0:
                                    new_articles += 1

                    except Exception as e:
                        logging.error(
                            f"Error processing WKYT Good Question article: {e}"
                        )

                conn.commit()

            print(
                f"✅ WKYT Good Questions scraping completed. Added {new_articles} new articles"
            )
            return new_articles

        except Exception as e:
            logging.error(f"Error scraping WKYT Good Questions: {e}")
            return 0

    def scrape_newsapi(self):
        """Scrape from NewsAPI.org for Lexington news"""
        try:
            # Get API key from environment
            api_key = os.getenv("NEWSAPI_ORG_KEY")
            if not api_key:
                print("⚠️ NEWSAPI_ORG_KEY not found in environment variables")
                return 0

            url = "https://newsapi.org/v2/everything"

            # Past week date range
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
                        published = article.get(
                            "publishedAt", datetime.now().isoformat()
                        )
                        source_name = article.get("source", {}).get("name", "NewsAPI")

                        if headline and article_url:
                            entry_data = {
                                "url": article_url,
                                "headline": headline,
                                "published": published,
                            }

                            entry_hash = self.generate_hash(entry_data)

                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO rss_data
                                (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    entry_hash,
                                    f"newsapi_{source_name}",
                                    article_url,
                                    headline,
                                    summary,
                                    published,
                                ),
                            )

                            if cursor.rowcount > 0:
                                new_articles += 1

                    except Exception as e:
                        logging.error(f"Error processing NewsAPI article: {e}")

                conn.commit()

            print(f"✅ NewsAPI scraping completed. Added {new_articles} new articles")
            return new_articles

        except Exception as e:
            logging.error(f"Error scraping NewsAPI: {e}")
            return 0

    def scrape_civiclex_news(self):
        """Scrape CivicLex news"""
        try:
            base_url = "https://civiclex.org/news"
            response = requests.get(base_url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")

            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Find news articles (adjust selector based on site structure)
                articles = soup.find_all("a", href=True)
                for article in articles:
                    try:
                        headline = article.get_text(strip=True)
                        if (
                            headline
                            and len(headline) > 10
                            and "/news/" in article["href"]
                        ):
                            article_url = urljoin(base_url, article["href"])
                            published = datetime.now().isoformat()

                            entry_data = {
                                "url": article_url,
                                "headline": headline,
                                "published": published,
                            }

                            entry_hash = self.generate_hash(entry_data)

                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO rss_data
                                (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    entry_hash,
                                    "civiclex",
                                    article_url,
                                    headline,
                                    "",
                                    published,
                                ),
                            )

                            if cursor.rowcount > 0:
                                new_articles += 1

                    except Exception as e:
                        logging.error(f"Error processing CivicLex article: {e}")

                conn.commit()

            print(f"✅ CivicLex scraping completed. Added {new_articles} new articles")
            return new_articles

        except Exception as e:
            logging.error(f"Error scraping CivicLex news: {e}")
            return 0

    def scrape_central_bank_center(self):
        """Scrape Central Bank Center (Rupp Arena) news - NOTE: This might belong in events instead"""
        try:
            url = "https://www.centralbankcenter.com/news"
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")

            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Find news articles
                info_divs = soup.find_all("div", class_="info")
                for div in info_divs:
                    try:
                        # Get date
                        date_span = div.find("span", class_="m-date__singleDate")
                        date_text = date_span.get_text(strip=True) if date_span else ""

                        # Get headline and URL
                        a_tag = div.find("a", href=True)
                        if a_tag:
                            headline = a_tag.get_text(strip=True)
                            article_url = urljoin(url, a_tag["href"])
                            published = datetime.now().isoformat()

                            if headline and len(headline) > 5:
                                entry_data = {
                                    "url": article_url,
                                    "headline": headline,
                                    "published": published,
                                }

                                entry_hash = self.generate_hash(entry_data)

                                cursor.execute(
                                    """
                                    INSERT OR IGNORE INTO rss_data
                                    (hash, source, url, headline, summary, published)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                    (
                                        entry_hash,
                                        "central_bank",
                                        article_url,
                                        headline,
                                        date_text,
                                        published,
                                    ),
                                )

                                if cursor.rowcount > 0:
                                    new_articles += 1

                    except Exception as e:
                        logging.error(
                            f"Error processing Central Bank Center article: {e}"
                        )

                conn.commit()

            print(
                f"✅ Central Bank Center scraping completed. Added {new_articles} new articles"
            )
            return new_articles

        except Exception as e:
            logging.error(f"Error scraping Central Bank Center: {e}")
            return 0

    def clean_lexgov_headline(self, headline):
        """Clean up LexGov headline by removing date and time"""
        import re

        pattern = r"^\w{3,4} \d{1,2}, \d{4} \d{1,2}:\d{2} [ap]\.m\.\s*"
        cleaned_headline = re.sub(pattern, "", headline)
        return cleaned_headline.strip()

    def scrape_lexington_gov_news(self):
        """Scrape Lexington Government news"""
        try:
            url = "https://www.lexingtonky.gov/news"
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")

            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Find all news items
                news_items = soup.find_all("div", class_="row")

                for item in news_items[:10]:
                    try:
                        url_tag = item.find("a")
                        date = item.find("time")
                        description_tag = item.find("div", class_="description")

                        if url_tag and date and description_tag:
                            href = url_tag["href"]
                            headline = url_tag.get_text(strip=True)

                            # Clean up the headline
                            cleaned_headline = self.clean_lexgov_headline(headline)

                            # Extract datetime or text
                            published = date.get("datetime", date.get_text(strip=True))
                            summary = description_tag.get_text(strip=True)

                            # Build full URL
                            if href.startswith("/"):
                                full_url = "https://www.lexingtonky.gov" + href
                            else:
                                full_url = href

                            if cleaned_headline and len(cleaned_headline) > 5:
                                entry_data = {
                                    "url": full_url,
                                    "headline": cleaned_headline,
                                    "published": published,
                                }

                                entry_hash = self.generate_hash(entry_data)

                                cursor.execute(
                                    """
                                    INSERT OR IGNORE INTO rss_data
                                    (hash, source, url, headline, summary, published)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                    (
                                        entry_hash,
                                        "lexington_gov",
                                        full_url,
                                        cleaned_headline,
                                        summary,
                                        published,
                                    ),
                                )

                                if cursor.rowcount > 0:
                                    new_articles += 1

                    except Exception as e:
                        logging.error(
                            f"Error processing Lexington Government article: {e}"
                        )

                conn.commit()

            print(
                f"✅ Lexington Government scraping completed. Added {new_articles} new articles"
            )
            return new_articles

        except Exception as e:
            logging.error(f"Error scraping Lexington Government news: {e}")
            return 0

    def scrape_newsdata_apis(self):
        """Scrape from NewsData.io and MediaStack APIs"""
        total_new = 0

        # NewsData.io API
        newsdata_key = os.getenv("NEWSDATA_API_KEY")
        if newsdata_key:
            total_new += self.scrape_newsdata_io(newsdata_key)
        else:
            print("⚠️ NEWSDATA_API_KEY not found - skipping NewsData.io")

        # MediaStack API
        mediastack_key = os.getenv("MEDIASTACK_API_KEY")
        if mediastack_key:
            total_new += self.scrape_mediastack(mediastack_key)
        else:
            print("⚠️ MEDIASTACK_API_KEY not found - skipping MediaStack")

        return total_new

    def scrape_newsdata_io(self, api_key):
        """Scrape from NewsData.io API"""
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                "apikey": api_key,
                "q": "Lexington Kentucky",
                "country": "us",
                "language": "en",
                "size": 10,
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") != "success":
                print(
                    f"⚠️ NewsData.io API error: {data.get('message', 'Unknown error')}"
                )
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
                            entry_data = {
                                "url": link,
                                "headline": title,
                                "published": pub_date,
                            }

                            entry_hash = self.generate_hash(entry_data)

                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO rss_data
                                (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    entry_hash,
                                    "newsdata_io",
                                    link,
                                    title,
                                    description,
                                    pub_date,
                                ),
                            )

                            if cursor.rowcount > 0:
                                new_articles += 1

                    except Exception as e:
                        logging.error(f"Error processing NewsData.io article: {e}")

                conn.commit()

            print(
                f"✅ NewsData.io scraping completed. Added {new_articles} new articles"
            )
            return new_articles

        except Exception as e:
            logging.error(f"Error scraping NewsData.io: {e}")
            return 0

    def scrape_mediastack(self, api_key):
        """Scrape from MediaStack API"""
        try:
            url = "http://api.mediastack.com/v1/news"
            params = {
                "access_key": api_key,
                "keywords": "Lexington Kentucky",
                "countries": "us",
                "languages": "en",
                "limit": 10,
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "error" in data:
                print(
                    f"⚠️ MediaStack API error: {data['error'].get('info', 'Unknown error')}"
                )
                return 0

            new_articles = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for article in data.get("data", []):
                    try:
                        title = article.get("title", "")
                        url_link = article.get("url", "")
                        description = article.get("description", "")
                        pub_date = article.get(
                            "published_at", datetime.now().isoformat()
                        )

                        if title and url_link and len(title) > 5:
                            entry_data = {
                                "url": url_link,
                                "headline": title,
                                "published": pub_date,
                            }

                            entry_hash = self.generate_hash(entry_data)

                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO rss_data
                                (hash, source, url, headline, summary, published)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    entry_hash,
                                    "mediastack",
                                    url_link,
                                    title,
                                    description,
                                    pub_date,
                                ),
                            )

                            if cursor.rowcount > 0:
                                new_articles += 1

                    except Exception as e:
                        logging.error(f"Error processing MediaStack article: {e}")

                conn.commit()

            print(
                f"✅ MediaStack scraping completed. Added {new_articles} new articles"
            )
            return new_articles

        except Exception as e:
            logging.error(f"Error scraping MediaStack: {e}")
            return 0

    def get_flair_id(self, headline):
        """Get flair ID based on headline content"""
        headline_lower = headline.lower()
        if any(
            word in headline_lower
            for word in [
                "shot",
                "shots",
                "shooter",
                "shooters",
                "shooting",
                "gunshot",
                "gunshots",
            ]
        ):
            return FLAIR_IDS["general"]
        elif "fire" in headline_lower:
            return FLAIR_IDS["fire"]
        elif any(
            word in headline_lower for word in ["homeless", "homelessness", "unhoused"]
        ):
            return FLAIR_IDS["homeless"]
        else:
            return None

    def init_reddit(self):
        """Initialize Reddit connection"""
        if not self.reddit:
            self.reddit = praw.Reddit(**REDDIT_CONFIG)
        return self.reddit

    def fetch_unposted_articles(self, limit=None):
        """Fetch unposted articles from database, ordered by newest first"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if limit:
                cursor.execute(
                    """
                    SELECT id, url, headline, source, published
                    FROM rss_data
                    WHERE posted = 0
                    ORDER BY published DESC, id DESC
                    LIMIT ?
                """,
                    (limit,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, url, headline, source, published
                    FROM rss_data
                    WHERE posted = 0
                    ORDER BY published DESC, id DESC
                """
                )
            return cursor.fetchall()

    def post_to_reddit(self, post_id, url, headline, source):
        """Post article to Reddit"""
        try:
            reddit = self.init_reddit()
            subreddit = reddit.subreddit(
                os.getenv("SUBREDDIT_NAME", "newsoflexingtonky")
            )

            # Create title with source prefix
            title = f"[{source.upper()}] {headline}"
            if len(title) > 300:  # Reddit title limit
                title = title[:297] + "..."

            submission = subreddit.submit(title=title, url=url)

            # Apply flair if applicable
            flair_id = self.get_flair_id(headline)
            if flair_id:
                try:
                    submission.flair.select(flair_id)
                except:
                    pass  # Flair failed, but post succeeded

            # Mark as posted in database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE rss_data SET posted = 1 WHERE id = ?", (post_id,)
                )
                conn.commit()

            logging.info(f"✅ Posted to Reddit: {headline[:50]}...")
            return True

        except Exception as e:
            logging.error(f"❌ Failed to post {headline[:50]}...: {e}")
            return False

    def post_unposted_articles(self, limit=5):
        """Post unposted articles to Reddit with rate limiting"""
        unposted = self.fetch_unposted_articles(limit)
        posted_count = 0

        if not unposted:
            print("📰 No unposted articles found")
            return 0

        print(f"📰 Posting {len(unposted)} articles to Reddit...")

        for post_id, url, headline, source, published in unposted:
            print(
                f"📅 Posting: [{source.upper()}] {headline[:50]}... (Published: {published[:16]})"
            )
            if self.post_to_reddit(post_id, url, headline, source):
                posted_count += 1
                posted_count += 1
                # Rate limiting - wait between posts
                time.sleep(2)

        print(f"✅ Posted {posted_count}/{len(unposted)} articles to Reddit")
        return posted_count

    def scrape_all(self):
        """Scrape all news sources"""
        total_new = 0
        total_new += self.scrape_rss_feeds()
        total_new += self.scrape_lexington_gov_news()  # Lexington Government scraper
        total_new += self.scrape_wkyt_news()
        total_new += self.scrape_wkyt_good_questions()
        total_new += self.scrape_newsapi()
        total_new += self.scrape_civiclex_news()
        total_new += self.scrape_central_bank_center()
        total_new += self.scrape_newsdata_apis()  # NewsData.io and MediaStack
        return total_new


def main():
    parser = argparse.ArgumentParser(description="News Scraper and Reddit Poster")
    parser.add_argument(
        "--scrape", action="store_true", help="Scrape news from all sources"
    )
    parser.add_argument(
        "--post", action="store_true", help="Post unposted articles to Reddit"
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="Limit number of Reddit posts"
    )
    parser.add_argument(
        "--all", action="store_true", help="Scrape and post (default if no args)"
    )

    args = parser.parse_args()

    news_manager = NewsManager()

    # Default action if no specific args
    if not any([args.scrape, args.post, args.all]):
        args.all = True

    if args.scrape or args.all:
        news_manager.scrape_all()

    if args.post or args.all:
        news_manager.post_unposted_articles(args.limit)


if __name__ == "__main__":
    main()
