"""
Pre-filters raw scraped posts and comments to strip out marketing fluff, speculative AGI futurism,
model benchmark noise, and LinkedIn self-promotion.
"""

import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class ContentFilter:
    """Pre-filters ingested items based on negative keyword rules and quality constraints."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.negative_keywords = config.get("negative_filters", {}).get("exclude_keywords", [])
        
        # Explicit Regex Patterns for Noise Categories
        self.marketing_pattern = re.compile(
            r"\b(buy now|webinar|whitepaper|download ebook|sponsored|register today|sign up for free|book a demo)\b",
            re.IGNORECASE
        )
        self.futurism_pattern = re.compile(
            r"\b(agi 2030|singularity|superintelligence|existential risk|doom scenario|paperclip maximizer)\b",
            re.IGNORECASE
        )
        self.benchmark_pattern = re.compile(
            r"\b(mmlu|humaneval|swe-bench|benchmark score|tokens per second|latency test)\b",
            re.IGNORECASE
        )
        self.self_promo_pattern = re.compile(
            r"\b(humbled and honored|thrilled to share|resume tips|how to pass interview|follow my newsletter|subscribe to my podcast)\b",
            re.IGNORECASE
        )

    def filter_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters out non-compliant items and returns cleaned, high-signal list."""
        filtered_items = []
        for item in items:
            is_valid, reason = self.evaluate_item(item)
            if is_valid:
                filtered_items.append(item)
            else:
                logger.debug(f"Discarding item '{item.get('title', '')[:40]}...': {reason}")

        logger.info(f"Filtered {len(items)} raw items down to {len(filtered_items)} high-signal candidates.")
        return filtered_items

    def evaluate_item(self, item: Dict[str, Any]) -> Tuple[bool, str]:
        """Evaluates a single item against all negative filters. Returns (is_valid, reason)."""
        title = item.get("title", "")
        body = item.get("body", "")
        comments_text = " ".join([c.get("body", "") for c in item.get("top_comments", [])])
        full_text = f"{title}\n{body}\n{comments_text}"

        # Rule 0: Forbidden PR / Marketing Syndication Networks (TipRanks, PRNewswire, etc.)
        url_text = (item.get("url") or item.get("permalink") or "").lower()
        pr_keywords = {"tipranks", "prnewswire", "businesswire", "globenewswire", "marketwatch", "benzinga", "seekingalpha", "techtarget", "accesswire"}
        if any(pr in url_text or pr in full_text.lower() for pr in pr_keywords):
            return False, "Excluded: Hard-rejected vendor PR / marketing syndication network"

        # Rule 1: Marketing / Vendor Fluff
        if self.marketing_pattern.search(full_text):
            return False, "Excluded: Vendor marketing / lead-gen whitepaper fluff"

        # Rule 2: Speculative Futurism
        if self.futurism_pattern.search(full_text):
            return False, "Excluded: Speculative AGI / futurism"

        # Rule 3: Benchmark Debates (unless organizational friction is present)
        if self.benchmark_pattern.search(full_text):
            # Check if there is explicit organizational context
            org_context_keywords = ["rollout", "enterprise", "manager", "policy", "employees", "workflow", "friction"]
            if not any(kw in full_text.lower() for kw in org_context_keywords):
                return False, "Excluded: Benchmark debate without organizational context"

        # Rule 4: Self-promotion & Career Advice
        if self.self_promo_pattern.search(full_text):
            return False, "Excluded: Self-promotion / career advice"

        # Rule 5: User-defined exclude keywords in config
        for kw in self.negative_keywords:
            if kw.lower() in full_text.lower():
                return False, f"Excluded: Matched negative keyword '{kw}'"

        # Rule 6: Minimal content check (must have title/body content)
        if len(full_text.strip()) < 30:
            return False, "Excluded: Content too short"

        return True, "Valid signal"
