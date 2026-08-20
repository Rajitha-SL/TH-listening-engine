"""
Web and RSS feed collector for tracking public job board postings, news feeds, and practitioner articles.
"""

import time
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

try:
    import feedparser
except ImportError:
    feedparser = None

logger = logging.getLogger(__name__)


class WebCollector:
    """Collects practitioner articles and public job postings via RSS feeds."""

    def fetch_rss_feeds(
        self,
        rss_sources: List[Dict[str, str]],
        keywords: Optional[List[str]] = None,
        days_lookback: int = 7,
        mock: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch and parse items from RSS feed URLs."""
        if mock or not feedparser:
            return self._get_mock_web_items()

        all_items: List[Dict[str, Any]] = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)

        for source in rss_sources:
            name = source.get("name", "Unknown Feed")
            url = source.get("url")
            if not url:
                continue

            logger.info(f"Ingesting RSS feed: {name}...")
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    # Determine date
                    published_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                    if published_parsed:
                        pub_dt = datetime.fromtimestamp(time.mktime(published_parsed), timezone.utc)
                    else:
                        pub_dt = datetime.now(timezone.utc)

                    if pub_dt < cutoff_date:
                        continue

                    title = getattr(entry, "title", "")
                    summary = getattr(entry, "summary", "")
                    link = getattr(entry, "link", "")

                    content_text = f"{title} {summary}".lower()
                    if keywords and not any(kw.lower() in content_text for kw in keywords):
                        continue

                    all_items.append({
                        "id": getattr(entry, "id", link),
                        "title": title,
                        "body": summary,
                        "subreddit": f"rss:{name}",
                        "author": getattr(entry, "author", "RSS Feed"),
                        "created_utc": pub_dt.timestamp(),
                        "created_date": pub_dt.strftime("%Y-%m-%d"),
                        "permalink": link,
                        "upvotes": 0,
                        "num_comments": 0,
                        "top_comments": [],
                        "source_type": "rss"
                    })
            except Exception as e:
                logger.warning(f"Error reading RSS feed '{name}': {e}")

        logger.info(f"Total raw RSS items ingested: {len(all_items)}")
        return all_items

    def _get_mock_web_items(self) -> List[Dict[str, Any]]:
        """Returns realistic mock web/job posting feed items."""
        now = datetime.now(timezone.utc)
        d1 = (now - timedelta(days=3)).strftime("%Y-%m-%d")

        return [
            {
                "id": "mock_rss_1",
                "title": "Job Posting: AI Change Management Lead - Enterprise Rollout",
                "body": "Seeking Change Manager to address widespread employee resistance to enterprise LLM mandates and train middle management across 10,000+ seat organization.",
                "subreddit": "rss:AI Change Management Jobs",
                "author": "Fortune 500 Enterprise",
                "created_utc": time.time() - 259200,
                "created_date": d1,
                "permalink": "https://careers.example.com/job/ai-change-lead-101",
                "upvotes": 0,
                "num_comments": 0,
                "top_comments": [],
                "source_type": "rss"
            }
        ]
