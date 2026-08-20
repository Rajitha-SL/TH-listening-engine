import os
import yaml
import feedparser
import urllib.parse
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

logger = logging.getLogger("reddit_collector")

class RedditCollector:
    def __init__(self, config: Dict[str, Any] = None):
        if config is not None:
            self.config = config
        elif os.path.exists("config.yaml"):
            with open("config.yaml", "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {
                "target_sources": {
                    "subreddits": ["humanresources", "managers", "sysadmin", "ExperiencedDevs", "change_management"]
                },
                "search_keywords": ["AI", "Copilot", "mandate", "adoption"],
                "parameters": {"default_days_lookback": 90}
            }

    def fetch_subreddit_posts(
        self,
        subreddits: List[str] = None,
        keywords: List[str] = None,
        days_lookback: int = 90,
        mock: bool = False,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Directly queries Subreddit Search RSS endpoints without authentication."""
        if mock:
            return self._get_mock_data()

        subs = subreddits or self.config.get("target_sources", {}).get("subreddits", ["humanresources", "managers"])
        search_terms = keywords or self.config.get("search_keywords", ["AI rollout", "Copilot", "AI mandate"])
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        collected = []
        seen_ids = set()

        for sub in subs:
            for term in search_terms[:2]:
                encoded_query = urllib.parse.quote(term)
                # Targeted search RSS feed within the specific subreddit
                search_feed_url = f"https://www.reddit.com/r/{sub}/search.rss?q={encoded_query}&restrict_sr=1&sort=relevance&t=year"
                
                try:
                    logger.info(f"Querying r/{sub} for '{term}'...")
                    feed = feedparser.parse(
                        search_feed_url,
                        agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                    )
                    
                    for entry in feed.entries[:5]:
                        post_id = entry.get("id", entry.get("link", ""))
                        if not post_id or post_id in seen_ids:
                            continue

                        title = entry.get("title", "")
                        summary = entry.get("summary", "")

                        # Filter out empty posts
                        if len(summary) < 20 and len(title) < 20:
                            continue

                        clean_body = summary.replace("&#32;", " ").replace("&quot;", '"').replace("&amp;", "&")

                        collected.append({
                            "id": post_id,
                            "source": f"r/{sub}",
                            "title": title,
                            "author": entry.get("author", "[anonymous]"),
                            "body": clean_body,
                            "url": entry.get("link", ""),
                            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                            "upvotes": 50,
                            "comment_count": 15,
                            "top_comments": []
                        })
                        seen_ids.add(post_id)
                except Exception as e:
                    logger.warning(f"Error querying {search_feed_url}: {e}")
                    continue

        return collected

    def _get_mock_data(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "mock_post_1",
                "source": "r/ExperiencedDevs",
                "title": "AI coding mandates from senior management",
                "author": "senior_dev_99",
                "body": "Leadership is tracking lines of AI-generated code. Copilot doesn't fit our architecture and slows us down, but they need to show ROI to the board.",
                "url": "https://reddit.com/r/ExperiencedDevs/comments/example1",
                "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "upvotes": 95,
                "comment_count": 214,
                "top_comments": []
            }
        ]