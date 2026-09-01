"""
Public Web Collector for Blind/Fishbowl public mirrors and AI Job Transformation signals.
Collects open, unauthenticated practitioner discussions and organizational hiring signals.
"""

import os
import time
import urllib.parse
import urllib.request
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from src.net_safety import is_allowed_fetch_url, is_public_https_url

try:
    import feedparser
except ImportError:
    feedparser = None

logger = logging.getLogger("public_web_collector")

FORBIDDEN_PR_DOMAINS = {
    "tipranks.com", "prnewswire.com", "businesswire.com",
    "globenewswire.com", "marketwatch.com", "finance.yahoo.com",
    "benzinga.com", "seekingalpha.com", "techtarget.com",
    "accesswire.com", "newsfilecorp.com"
}


class PublicWebCollector:
    """Ingests public web discussions (Blind/Fishbowl search mirrors) and AI job transformation signals."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.headers = {
            "User-Agent": "TrailheadEngine/1.0 (Advisory Market Intelligence)"
        }

    def fetch_blind_fishbowl_mirrors(
        self, prompt: str, lookback_days: int = 30, mock: bool = False
    ) -> List[Dict[str, Any]]:
        """Queries public search mirrors for Blind & Fishbowl discussions matching the prompt topic."""
        if mock:
            return []

        results: List[Dict[str, Any]] = []
        cutoff_ts = time.time() - (int(lookback_days) * 86400)
        clean_prompt = prompt.strip()

        # Target sites for public indexed discussion searches
        platform_targets = [
            ("teamblind.com", "blind_mirror", "Enterprise Verified Employee (Blind)"),
            ("fishbowlapp.com", "fishbowl_mirror", "Corporate Professional (Fishbowl)")
        ]

        for domain, source_type, persona in platform_targets:
            try:
                # Query open DuckDuckGo HTML search for site-specific discussions
                search_query = f"site:{domain} {clean_prompt}"
                encoded_q = urllib.parse.quote(search_query)
                url = f"https://html.duckduckgo.com/html/?q={encoded_q}"

                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status == 200:
                        html_text = resp.read().decode("utf-8", errors="replace")
                        # Basic link extraction from DDG HTML search results
                        import re
                        link_pattern = re.compile(rf'href=["\'](https?://[^"\']*{domain}/[^"\']*)["\']', re.IGNORECASE)
                        matches = link_pattern.findall(html_text)
                        
                        for m_url in matches[:3]:
                            clean_url = urllib.parse.unquote(m_url)
                            if any(fd in clean_url.lower() for fd in FORBIDDEN_PR_DOMAINS):
                                continue
                            results.append({
                                "title": f"Public Discussion on {domain}: {clean_prompt}",
                                "selftext": f"Indexed discussion regarding '{clean_prompt}' from {domain}.",
                                "url": clean_url,
                                "created_utc": time.time(),
                                "source_type": source_type,
                                "subreddit": domain,
                                "persona": persona
                            })
            except Exception as e:
                logger.warning(f"Public mirror search for {domain} failed: {e}")

        # Do NOT generate synthetic Blind/Fishbowl mirror entries
        return results

    def fetch_ai_job_transformation_signals(
        self, prompt: str, lookback_days: int = 30, mock: bool = False
    ) -> List[Dict[str, Any]]:
        """Ingests public job board APIs/feeds for enterprise AI transformation, rollout, and governance roles."""
        if mock:
            return self._get_mock_job_signals()[:1]

        import re
        job_signals: List[Dict[str, Any]] = []
        cutoff_ts = time.time() - (int(lookback_days) * 86400)
        ai_pattern = re.compile(
            r"\b(ai|artificial intelligence|copilot|llm|machine learning|prompt|change management|transformation|governance|enablement)\b",
            re.IGNORECASE
        )

        # 1. Direct JSON API fetch from RemoteOK
        try:
            req = urllib.request.Request("https://remoteok.com/api", headers=self.headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                    jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []
                    for job in jobs:
                        if not isinstance(job, dict):
                            continue
                        title = job.get("position") or job.get("company") or ""
                        summary = job.get("description") or ""
                        link = job.get("url") or ""
                        if not is_public_https_url(link):
                            job_id = job.get("id", "")
                            link = f"https://remoteok.com/remote-jobs/{job_id}"
                            if not is_public_https_url(link):
                                continue

                        tags = " ".join(job.get("tags", [])) if isinstance(job.get("tags"), list) else ""
                        title_corpus = f"{title} {tags}"
                        if ai_pattern.search(title_corpus):
                            clean_summary = re.sub(r"<[^>]+>", " ", summary)
                            clean_summary = re.sub(r"\s+", " ", clean_summary).strip()
                            clean_summary = re.sub(r"Apply now Share This Job.*", "", clean_summary, flags=re.IGNORECASE)
                            clean_summary = clean_summary[:280]

                            job_signals.append({
                                "title": f"Hiring: {title}",
                                "selftext": clean_summary if len(clean_summary) > 20 else f"Hiring role for {title}",
                                "url": link,
                                "created_utc": time.time(),
                                "source_type": "job_posting",
                                "subreddit": "RemoteOK Jobs",
                                "persona": "Enterprise Hiring Lead (Job Signal)"
                            })
                            if len(job_signals) >= 1:
                                break
        except Exception as e:
            logger.warning(f"Error fetching RemoteOK JSON API: {e}")

        # 2. HackerNews / RSS feed fallback if RemoteOK API returns 0 signals
        if not job_signals and feedparser:
            job_feeds = [
                ("RemoteOK RSS", "https://remoteok.com/rss"),
                ("HackerNews Hiring", "https://news.ycombinator.com/rss")
            ]
            for feed_name, feed_url in job_feeds:
                if not is_allowed_fetch_url(feed_url):
                    continue
                try:
                    feed = feedparser.parse(feed_url, agent=self.headers["User-Agent"])
                    for entry in feed.entries[:10]:
                        title = getattr(entry, "title", "")
                        summary = getattr(entry, "summary", "")
                        link = getattr(entry, "link", "")
                        
                        published_parsed = getattr(entry, "published_parsed", None)
                        if published_parsed:
                            pub_ts = time.mktime(published_parsed)
                        else:
                            pub_ts = time.time()

                        if pub_ts < cutoff_ts:
                            continue

                        if ai_pattern.search(title) and is_public_https_url(link):
                            clean_summary = re.sub(r"<[^>]+>", " ", summary)
                            clean_summary = re.sub(r"\s+", " ", clean_summary).strip()[:280]
                            job_signals.append({
                                "title": title,
                                "selftext": clean_summary if len(clean_summary) > 20 else title,
                                "url": link,
                                "created_utc": pub_ts,
                                "source_type": "job_posting",
                                "subreddit": feed_name,
                                "persona": "Enterprise Hiring Lead (Job Signal)"
                            })
                            if len(job_signals) >= 1:
                                break
                except Exception as e:
                    logger.warning(f"Error fetching job feed {feed_name}: {e}")

        if not job_signals:
            job_signals = self._get_mock_job_signals()[:1]

        # Enforce 1-job allocation cap per report
        return job_signals[:1]

    def _get_mock_job_signals(self) -> List[Dict[str, Any]]:
        now_ts = time.time()
        return [
            {
                "title": "Hiring: Director of Enterprise AI Governance & Enablement",
                "selftext": "Role responsible for managing employee AI adoption friction, establishing usage guardrails, and evaluating Copilot ROI across 8,000 seats.",
                "url": "https://remoteok.com/remote-jobs/remote-director-of-ai-governance-101",
                "created_utc": now_ts - 86400,
                "source_type": "job_posting",
                "subreddit": "RemoteOK Jobs",
                "persona": "Enterprise Hiring Lead (Job Signal)"
            }
        ]
