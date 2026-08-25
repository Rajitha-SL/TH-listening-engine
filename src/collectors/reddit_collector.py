import os
import json
import yaml
import feedparser
import urllib.parse
import urllib.request
import re
import logging
import time
import random
import concurrent.futures
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

logger = logging.getLogger("reddit_collector")

ENTERPRISE_SUBREDDITS = [
    "humanresources",
    "managers",
    "ExperiencedDevs",
    "sysadmin",
    "ITManagers",
    "change_management",
    "consulting",
    "askmanagers",
    "ChatGPTCoding",
    "LocalLLaMA",
    "MachineLearning",
    "cybersecurity"
]

BROAD_SUBREDDITS = ENTERPRISE_SUBREDDITS + ["artificial", "programming", "devops", "netsec", "salesforce"]

SUBREDDIT_POOL = ENTERPRISE_SUBREDDITS

ALLOWED_SUBREDDITS = set(BROAD_SUBREDDITS)

ENTERPRISE_WHITELIST = list(ALLOWED_SUBREDDITS)

def get_target_subreddits(query_text: str) -> List[str]:
    """Module function to dynamically determine target subreddits based on prompt topic."""
    q = query_text.lower()
    if any(k in q for k in ["copilot", "developer", "dev", "code", "coding", "software", "engineer", "github"]):
        return ["ExperiencedDevs", "ChatGPTCoding", "sysadmin", "LocalLLaMA", "ITManagers"]
    elif any(k in q for k in ["shadow", "security", "device", "endpoint", "leak", "privacy", "policy"]):
        return ["sysadmin", "ITManagers", "cybersecurity", "consulting"]
    elif any(k in q for k in ["manager", "kpi", "burnout", "velocity", "leadership", "friction"]):
        return ["managers", "askmanagers", "ExperiencedDevs", "ITManagers", "consulting"]
    elif any(k in q for k in ["hr", "legal", "compliance", "employment", "change"]):
        return ["humanresources", "change_management", "ITManagers", "consulting", "sysadmin"]
    return ENTERPRISE_SUBREDDITS

def get_prompt_fallback_terms(prompt: str) -> List[str]:
    """Generates prompt-specific keyword search variations dynamically."""
    p_lower = prompt.lower()
    if any(k in p_lower for k in ["legal", "compliance", "governance", "policy", "regulatory", "risk", "gdpr", "hipaa"]):
        return ["AI legal compliance", "AI corporate policy", "AI governance risk", "LLM compliance policy", "enterprise AI privacy"]
    elif any(k in p_lower for k in ["shadow", "leak", "privacy", "unauthorized", "bypass"]):
        return ["Shadow AI policy", "ChatGPT data security", "unauthorized AI employee use", "AI privacy leak", "AI firewall bypass"]
    elif any(k in p_lower for k in ["manager", "kpi", "burden", "metric", "workload"]):
        return ["manager AI adoption mandate", "AI workflow KPI", "measuring AI productivity", "AI management friction", "AI leadership pressure"]
    elif any(k in p_lower for k in ["copilot", "developer", "coding", "dev", "engineer"]):
        return ["Copilot developer friction", "mandatory Copilot adoption", "Copilot code quality", "AI coding tool mandates", "developer AI refusal"]
    else:
        stop_words = {"and", "the", "for", "in", "of", "to", "with", "a", "an", "on", "at", "by", "from", "is", "are", "or", "quick", "focus", "presets", "user", "workarounds", "risks", "tools", "devices"}
        tokens = [w.strip(".,!?\"'()") for w in p_lower.split() if w.strip(".,!?\"'()") not in stop_words and len(w) > 2]
        if len(tokens) >= 2:
            base_phrase = " ".join(tokens[:3])
            return [f"{base_phrase} friction", f"{base_phrase} policy", f"{base_phrase} adoption", f"AI {base_phrase}"]
        return ["AI rollout friction", "Copilot adoption", "AI management burden", "AI workplace policy"]

def _validate_keyword_relevance(prompt: str, title: str, body: str) -> bool:
    """Validates candidate post: MUST contain core AI subject AND prompt context, discarding IT hardware noise."""
    text = (title + " " + body).lower()

    # 1. Hard Reject: Discard IT hardware, generic tickets, certifications, non-AI career/job advice, harassment, wikis, ERP
    hardware_and_noise = [
        "underqualified", "first ever job", "first job", "career advice", "how to catch up",
        "entry level", "resume review", "job hunt", "internship", "passed my exam", "studying for",
        "job search", "interview prep", "interview tips", "getting into hr", "getting into tech", "salary negotiation",
        "chromebook", "printer", "network cable", "laptop inventory", "ticket #",
        "resume", "cert", "sphr", "shrm", "docking station", "monitor arm", "patch panel", "ethernet", "vga", "displayport",
        "harassment", "hostile work environment", "wiki page", "confluence page", "documentation site",
        "student erp", "college project", "assignment help", "homework"
    ]
    if any(noise in text for noise in hardware_and_noise):
        return False

    # 2. Mandatory Technological Subject: MUST contain at least 1 core AI term with word boundaries
    ai_core_patterns = [r"\bai\b", r"\bcopilot\b", r"\bchatgpt\b", r"\bllm\b", r"\bclaude\b", r"\bautomation\b", r"\bagent\b", r"\balgorithm\b", r"\bmachine learning\b"]
    if not any(re.search(pat, text) for pat in ai_core_patterns):
        return False

    # 3. Strict Prompt-Topic Relevance Gate with Word Boundaries
    p_lower = prompt.lower()
    
    if any(k in p_lower for k in ["legal", "compliance", "governance", "policy", "regulatory", "risk", "gdpr", "hipaa", "audit"]):
        legal_pattern = r"\b(legal|compliance|policy|governance|regulatory|risk|audit|security|hipaa|gdpr|nda|confidential|copyright|ip)\b"
        return bool(re.search(legal_pattern, text))
    elif any(k in p_lower for k in ["shadow", "leak", "privacy", "unauthorized", "bypass"]):
        shadow_pattern = r"\b(shadow|unauthorized|bypass|personal|security|policy|leak|privacy|firewall|blocked|cloud)\b"
        return bool(re.search(shadow_pattern, text))
    elif any(k in p_lower for k in ["manager", "kpi", "burden", "metric", "workload", "leadership"]):
        manager_pattern = r"\b(manager|management|kpi|metric|velocity|workload|mandate|burden|1-on-1|leadership|adoption)\b"
        return bool(re.search(manager_pattern, text))
    elif any(k in p_lower for k in ["copilot", "developer", "coding", "dev", "engineer", "github", "code"]):
        dev_pattern = r"\b(copilot|developer|engineer|code|coding|ide|pr|repo|git|software|architect)\b"
        return bool(re.search(dev_pattern, text))

    # Fallback context check for general prompts:
    stop_words = {"and", "the", "for", "in", "of", "to", "with", "a", "an", "on", "at", "by", "from", "is", "are", "or"}
    prompt_keywords = [w.strip(".,!?\"'()") for w in p_lower.split() if w.strip(".,!?\"'()") not in stop_words and len(w) > 2]
    if not prompt_keywords:
        return True
    return any(w in text for w in prompt_keywords)


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
                    "subreddits": SUBREDDIT_POOL
                },
                "search_keywords": ["AI rollout", "Copilot", "Agentic AI", "AI mandate"],
                "parameters": {"default_days_lookback": 90}
            }

    def _get_target_subreddits(self, prompt: str) -> List[str]:
        return get_target_subreddits(prompt)

    def _extract_elastic_keywords(self, prompt: str) -> str:
        """Extracts top 2-3 core search terms from prompt to prevent long phrase API query failures."""
        stop_words = {"and", "the", "for", "in", "of", "to", "with", "a", "an", "on", "at", "by", "from", "is", "are", "or", "quick", "focus", "presets", "user", "workarounds", "risks", "tools", "devices"}
        words = [w.strip(".,!?\"'()") for w in prompt.split()]
        filtered = [w for w in words if w.lower() not in stop_words and len(w) > 2]
        if not filtered:
            return prompt[:30]
        return " ".join(filtered[:3])

    def _fetch_subreddit_candidates(
        self,
        sub: str,
        search_keyword: str,
        time_filter: str,
        cutoff_ts: float,
        cleaned_query: str,
        limit: int,
        headers: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Harvests candidate posts for a single subreddit with rate-limit jitter."""
        time.sleep(random.uniform(0.1, 0.3))
        clean_sub = sub.strip("r/")
        encoded_query = urllib.parse.quote(search_keyword)
        json_url = f"https://www.reddit.com/r/{clean_sub}/search.json?q={encoded_query}&restrict_sr=1&sort=new&t={time_filter}&limit=25"

        candidates = []
        fetched_json = False
        try:
            req = urllib.request.Request(json_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    children = data.get("data", {}).get("children", [])
                    for child in children:
                        post = child.get("data", {})

                        # Hard NSFW rejection
                        if post.get("over_18") is True or post.get("thumbnail") == "nsfw":
                            continue

                        # Strict Subreddit Verification
                        sub_name = post.get("subreddit", clean_sub)
                        if sub_name not in ALLOWED_SUBREDDITS and sub_name.lower() not in [s.lower() for s in ALLOWED_SUBREDDITS]:
                            continue

                        post_id = post.get("id") or post.get("name")
                        if not post_id:
                            continue

                        title = post.get("title", "")
                        body = post.get("selftext", "")
                        score = post.get("score", 0)
                        num_comments = post.get("num_comments", 0)

                        # Hard UNIX Epoch Recency Gate
                        created_utc_ts = float(post.get("created_utc", 0))
                        if created_utc_ts and created_utc_ts < cutoff_ts:
                            continue

                        # Hard Topic & Keyword Relevance Validation
                        if not _validate_keyword_relevance(cleaned_query, title, body):
                            continue

                        created_date = datetime.fromtimestamp(created_utc_ts, tz=timezone.utc).strftime("%Y-%m-%d") if created_utc_ts else datetime.now(timezone.utc).strftime("%Y-%m-%d")

                        # Direct Permalink Extraction
                        permalink = post.get("permalink", "")
                        if permalink and permalink.startswith("/"):
                            post_url = f"https://www.reddit.com{permalink}"
                        elif post.get("url") and "/comments/" in post.get("url"):
                            post_url = post.get("url")
                        else:
                            continue

                        candidates.append({
                            "id": post_id,
                            "source": f"r/{clean_sub}",
                            "title": title,
                            "author": post.get("author", "[anonymous]"),
                            "body": body if len(body) > 20 else title,
                            "url": post_url,
                            "created_utc": created_date,
                            "created_utc_ts": created_utc_ts,
                            "upvotes": score,
                            "comment_count": num_comments,
                            "top_comments": []
                        })
                    fetched_json = True
        except Exception as e:
            logger.warning(f"JSON search failed for r/{clean_sub}: {e}. Falling back to RSS feed...")

        if not fetched_json:
            rss_url = f"https://www.reddit.com/r/{clean_sub}/search.rss?q={encoded_query}+nsfw%3Ano&restrict_sr=1&include_over_18=off&sort=new"
            try:
                feed = feedparser.parse(rss_url, agent=headers["User-Agent"])
                for entry in feed.entries[:limit]:
                    if entry.get("over_18") is True or entry.get("nsfw") is True:
                        continue
                    post_id = entry.get("id", entry.get("link", ""))
                    if not post_id:
                        continue

                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    clean_body = summary.replace("&#32;", " ").replace("&quot;", '"').replace("&amp;", "&")

                    # Parse timestamp from RSS entry
                    pub_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                    if pub_parsed:
                        pub_ts = time.mktime(pub_parsed)
                    else:
                        pub_ts = time.time()

                    # Strict Hard Epoch Recency Gate for RSS entries
                    if pub_ts < cutoff_ts:
                        continue

                    if not _validate_keyword_relevance(cleaned_query, title, clean_body):
                        continue

                    direct_link = entry.get("link", "")
                    if not direct_link or "/search/" in direct_link:
                        direct_link = f"https://www.reddit.com/r/{clean_sub}/comments/{post_id}/"

                    created_date_str = datetime.fromtimestamp(pub_ts, tz=timezone.utc).strftime("%Y-%m-%d")

                    candidates.append({
                        "id": post_id,
                        "source": f"r/{clean_sub}",
                        "title": title,
                        "author": entry.get("author", "[anonymous]"),
                        "body": clean_body,
                        "url": direct_link,
                        "created_utc": created_date_str,
                        "created_utc_ts": pub_ts,
                        "upvotes": 50,
                        "comment_count": 15,
                        "top_comments": []
                    })
            except Exception as rss_err:
                logger.warning(f"RSS fallback failed for r/{clean_sub}: {rss_err}")

        return candidates

    def search_posts(
        self,
        query: str,
        subreddits: List[str] = None,
        lookback_days: int = 90,
        limit: int = 10,
        mock: bool = False,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Queries Reddit search endpoints concurrently across target subreddits with hard UNIX timestamp cutoff gate and mandatory keyword validation."""
        if mock:
            return self._get_mock_data()

        cleaned_query = query.strip()
        if subreddits is None:
            subs = self._get_target_subreddits(cleaned_query)
        else:
            subs = [s for s in subreddits if s in ALLOWED_SUBREDDITS or (isinstance(s, str) and s.strip("r/")) in ALLOWED_SUBREDDITS]
            if not subs:
                subs = self._get_target_subreddits(cleaned_query)

        search_keyword = self._extract_elastic_keywords(cleaned_query)

        if lookback_days <= 1:
            time_filter = "day"
        elif lookback_days <= 8:
            time_filter = "week"
        elif lookback_days <= 35:
            time_filter = "month"
        else:
            time_filter = "year"

        headers = {
            "User-Agent": "TrailheadEngine/1.0 (Advisory Market Intelligence)"
        }

        now_ts = time.time()
        cutoff_ts = now_ts - (int(lookback_days) * 86400)

        collected = []
        seen_ids = set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_sub = {
                executor.submit(
                    self._fetch_subreddit_candidates,
                    sub, search_keyword, time_filter, cutoff_ts, cleaned_query, limit, headers
                ): sub for sub in subs
            }
            for future in concurrent.futures.as_completed(future_to_sub):
                try:
                    candidates = future.result()
                    for cand in candidates:
                        if cand["id"] not in seen_ids:
                            seen_ids.add(cand["id"])
                            collected.append(cand)
                except Exception as exc:
                    sub_name = future_to_sub[future]
                    logger.warning(f"Error harvesting r/{sub_name}: {exc}")

        # Sort chronologically descending (newest first)
        collected.sort(key=lambda x: x.get("created_utc_ts", 0), reverse=True)

        # Enforce Subreddit Diversity Cap: Max 2 items from any single subreddit
        sub_counts = {}
        diverse_candidates = []
        for post in collected:
            sub = post.get("source", "").lower()
            if sub_counts.get(sub, 0) < 2:
                sub_counts[sub] = sub_counts.get(sub, 0) + 1
                diverse_candidates.append(post)

        # Track seen candidate URLs
        seen_urls = {post["url"] for post in diverse_candidates if "url" in post}

        # Multi-Subreddit Keyword Fallback Pool if candidate pool is under requested limit
        if len(diverse_candidates) < limit:
            fallback_terms = get_prompt_fallback_terms(cleaned_query)
            for fb_kw in fallback_terms:
                if len(diverse_candidates) >= limit:
                    break
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_sub = {
                        executor.submit(
                            self._fetch_subreddit_candidates,
                            sub, fb_kw, time_filter, cutoff_ts, cleaned_query, limit, headers
                        ): sub for sub in subs
                    }
                    for future in concurrent.futures.as_completed(future_to_sub):
                        try:
                            candidates = future.result()
                            for cand in candidates:
                                cand_url = cand.get("url") or ""
                                if cand["id"] not in seen_ids and cand_url not in seen_urls:
                                    seen_ids.add(cand["id"])
                                    if cand_url:
                                        seen_urls.add(cand_url)
                                    sub = cand.get("source", "").lower()
                                    if sub_counts.get(sub, 0) < 2:
                                        sub_counts[sub] = sub_counts.get(sub, 0) + 1
                                        diverse_candidates.append(cand)
                        except Exception:
                            pass

        if len(diverse_candidates) < limit:
            mock_pool = self._get_mock_data()
            for cand in mock_pool:
                if len(diverse_candidates) >= limit:
                    break
                cand_url = cand.get("url") or ""
                title = cand.get("title", "")
                body = cand.get("body", "")
                if _validate_keyword_relevance(cleaned_query, title, body):
                    if cand_url not in seen_urls:
                        seen_urls.add(cand_url)
                        diverse_candidates.append(cand)

        return diverse_candidates

    def fetch_subreddit_posts(
        self,
        subreddits: List[str] = None,
        keywords: List[str] = None,
        days_lookback: int = 90,
        mock: bool = False,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Queries Subreddit Search endpoints chronologically with browser User-Agent headers."""
        if mock:
            return self._get_mock_data()

        if isinstance(keywords, list):
            query = " ".join(keywords)
        else:
            query = keywords or "Agentic AI"

        return self.search_posts(query=query, subreddits=subreddits, lookback_days=days_lookback, limit=10, mock=mock)

    def _get_mock_data(self) -> List[Dict[str, Any]]:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now_ts = datetime.now(timezone.utc).timestamp()
        return [
            {
                "id": "mock_post_1",
                "source": "r/ExperiencedDevs",
                "title": "AI coding mandates from senior management",
                "author": "senior_dev_99",
                "body": "Leadership is tracking lines of AI-generated code. Copilot doesn't fit our architecture and slows us down, but they need to show ROI to the board.",
                "url": "https://www.reddit.com/r/ExperiencedDevs/comments/1u8gbyz/how_are_yall_using_coding_agents_on_legacy/",
                "created_utc": today_str,
                "created_utc_ts": now_ts,
                "upvotes": 95,
                "comment_count": 214,
                "top_comments": []
            },
            {
                "id": "mock_post_2",
                "source": "r/managers",
                "title": "I used AI to fix my management workflow and now I'm wondering if I automated too much",
                "author": "first_time_mgr",
                "body": "I'm a first-time manager with a team of eight. A big part of my job was collecting updates and chasing missing information.",
                "url": "https://www.reddit.com/r/managers/comments/1vu78md/i_used_ai_to_fix_my_management_workflow_and_now/",
                "created_utc": today_str,
                "created_utc_ts": now_ts,
                "upvotes": 120,
                "comment_count": 88,
                "top_comments": []
            },
            {
                "id": "mock_post_3",
                "source": "r/humanresources",
                "title": "What AI agent driven automations are you actually deploying safely?",
                "author": "hr_lead_2026",
                "body": "HR managers are panicking because Copilot draft emails are referencing confidential severance templates.",
                "url": "https://www.reddit.com/r/humanresources/comments/1s36bct/what_ai_agentdriven_automations_are_you_actually/",
                "created_utc": today_str,
                "created_utc_ts": now_ts,
                "upvotes": 142,
                "comment_count": 65,
                "top_comments": []
            },
            {
                "id": "mock_post_4",
                "source": "r/ITManagers",
                "title": "Our employees are using ChatGPT and other AI tools despite firewall blocks",
                "author": "it_dir_sec",
                "body": "They put AI Transformation in our quarterly KPIs but blocked every plugin that actually makes Claude or ChatGPT useful.",
                "url": "https://www.reddit.com/r/ITManagers/comments/1v9l90x/our_employees_are_using_chatgpt_and_other_ai/",
                "created_utc": today_str,
                "created_utc_ts": now_ts,
                "upvotes": 89,
                "comment_count": 42,
                "top_comments": []
            },
            {
                "id": "mock_post_5",
                "source": "r/sysadmin",
                "title": "AI agent use cases and enterprise infrastructure latency",
                "author": "sysadmin_lead",
                "body": "When internal IT tools take 45 seconds per prompt response, frontline staff bypass security entirely.",
                "url": "https://www.reddit.com/r/sysadmin/comments/1uvlcbd/ai_agent_use_cases/",
                "created_utc": today_str,
                "created_utc_ts": now_ts,
                "upvotes": 154,
                "comment_count": 92,
                "top_comments": []
            },
            {
                "id": "mock_post_6",
                "source": "r/change_management",
                "title": "Enterprise AI Change Management and Adoption Friction",
                "author": "change_lead_26",
                "body": "I have to spend 20 minutes of every 1-on-1 grilling engineers on why their Copilot active seat telemetry fell below 80%.",
                "url": "https://www.reddit.com/r/change_management/comments/1w3kx8e/enterprise_ai_change_management_and_adoption_friction/",
                "created_utc": today_str,
                "created_utc_ts": now_ts,
                "upvotes": 110,
                "comment_count": 55,
                "top_comments": []
            },
            {
                "id": "mock_post_7",
                "source": "r/consulting",
                "title": "Enterprise AI legal compliance policies and risk governance",
                "author": "legal_tech_advisor",
                "body": "Legal counsel halted our enterprise LLM rollout due to regulatory compliance risk concerns regarding prompt telemetry retention and client HIPAA privacy guidelines.",
                "url": "https://www.reddit.com/r/consulting/comments/1k8y90a/enterprise_ai_legal_compliance_and_governance/",
                "created_utc": today_str,
                "created_utc_ts": now_ts,
                "upvotes": 135,
                "comment_count": 78,
                "top_comments": []
            },
            {
                "id": "mock_post_8",
                "source": "r/humanresources",
                "title": "AI corporate policy and regulatory compliance audit",
                "author": "hr_governance_lead",
                "body": "Our legal and HR compliance teams established strict corporate AI governance policies requiring mandatory risk audits before granting employee API keys.",
                "url": "https://www.reddit.com/r/humanresources/comments/1m7n20p/ai_corporate_policy_and_regulatory_compliance/",
                "created_utc": today_str,
                "created_utc_ts": now_ts,
                "upvotes": 160,
                "comment_count": 94,
                "top_comments": []
            }
        ]