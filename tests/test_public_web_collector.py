import pytest
import time
from src.collectors.public_web_collector import PublicWebCollector


def test_public_web_collector_mock_mirrors():
    collector = PublicWebCollector()
    items = collector.fetch_blind_fishbowl_mirrors(prompt="Copilot developer friction", lookback_days=7, mock=True)
    # Zero synthetic mirror policy: returns empty list if no unauthenticated public search results are found
    assert isinstance(items, list)
    assert len(items) == 0


def test_public_web_collector_mock_job_signals():
    collector = PublicWebCollector()
    signals = collector.fetch_ai_job_transformation_signals(prompt="Copilot developer friction", lookback_days=7, mock=True)
    assert len(signals) >= 1
    for sig in signals:
        assert "url" in sig
        assert sig["url"].startswith("http")
        assert "careers.enterprise.com" not in sig["url"]
        assert sig["source_type"] == "job_posting"
        assert "Hiring" in sig["title"] or "Governance" in sig["title"] or "Enablement" in sig["title"]
        assert "persona" in sig
        assert isinstance(sig["created_utc"], float)


def test_public_web_collector_recency_cutoff():
    collector = PublicWebCollector()
    signals = collector.fetch_ai_job_transformation_signals(prompt="AI rollout", lookback_days=30, mock=True)
    cutoff = time.time() - (30 * 86400)
    for sig in signals:
        assert sig["created_utc"] >= cutoff


def test_job_allocation_cap_and_regex_word_boundary():
    collector = PublicWebCollector()
    signals = collector.fetch_ai_job_transformation_signals(prompt="Copilot developer friction", lookback_days=7, mock=True)
    # Enforce maximum 1 job signal allocation cap per report
    assert len(signals) <= 1

    import re
    ai_pattern = re.compile(
        r"\b(ai|artificial intelligence|copilot|llm|machine learning|prompt|change management|transformation|governance|enablement)\b",
        re.IGNORECASE
    )
    # Non-AI jobs containing 'ai' inside words must be rejected by word boundaries
    non_ai_titles = ["Team Manager Newry Extra", "Tesco Shift Manager", "Across all departments", "Main Retail Associate"]
    for title in non_ai_titles:
        assert not ai_pattern.search(title)

    # Valid AI job titles must match
    ai_titles = ["Director of Enterprise AI Governance", "Copilot Enablement Lead", "Prompt Engineer"]
    for title in ai_titles:
        assert ai_pattern.search(title)
