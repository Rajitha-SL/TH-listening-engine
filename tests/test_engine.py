"""
Mock Test Suite for Trailhead Market Listening Engine matching Barbara's 4 Gold-Standard Test Cases.
"""

import os
import json
import tempfile
import pytest
from datetime import datetime, timezone

from src.processors.filter import ContentFilter
from src.processors.claude_synthesizer import ClaudeSynthesizer, SynthesisReport, EvidenceFinding
from src.storage.memory_manager import MemoryManager
from src.formatters.markdown_builder import MarkdownBuilder


@pytest.fixture
def sample_config():
    return {
        "version": "1.0",
        "target_sources": {
            "subreddits": ["humanresources", "managers", "sysadmin"],
            "rss_feeds": []
        },
        "negative_filters": {
            "exclude_keywords": ["buy now", "webinar", "AGI 2030", "humbled and honored"]
        },
        "hypotheses": {
            "H1": {"name": "Impatience & Tool Friction Shift", "description": "Shift to tool friction."},
            "H2": {"name": "Middle Management Burden", "description": "Middle managers carrying rollout burden."},
            "H3": {"name": "Executive Mandate vs Operational Reality Gap", "description": "Mandate gap."},
            "EMERGING": {"name": "Emerging Friction Pattern", "description": "Unlisted friction."}
        },
        "synthesis": {
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.1
        }
    }


@pytest.fixture
def mock_gold_standard_items():
    """Barbara's 4 Gold-Standard Test Case Items."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        {
            "id": "item_1",
            "title": "Copilot draft emails referencing confidential severance templates",
            "body": "Leadership mandated M365 Copilot for all 4,000 employees last month without any training or security guidelines. HR managers are panicking because Copilot draft emails are referencing confidential severance templates.",
            "subreddit": "humanresources",
            "author": "hr_dir_midmarket",
            "created_utc": 1700000000,
            "created_date": today,
            "permalink": "https://www.reddit.com/r/humanresources/comments/item_1/",
            "upvotes": 142,
            "top_comments": [
                {
                    "author": "senior_hr_bp",
                    "body": "They put 'AI Transformation' in our quarterly KPIs but blocked every plugin that actually makes Claude or ChatGPT useful.",
                    "upvotes": 89,
                    "created_date": today,
                    "permalink": "https://www.reddit.com/r/humanresources/comments/item_1/comment/c1"
                }
            ]
        },
        {
            "id": "item_2",
            "title": "Middle managers carrying the brunt of mandatory AI adoption metrics",
            "body": "VP declared 100% team usage of enterprise AI tools by end of Q3. My devs refuse to use the corporate wrapper because it hallucinates boilerplate and truncates context windows.",
            "subreddit": "managers",
            "author": "engineering_mgr_77",
            "created_utc": 1700000100,
            "created_date": today,
            "permalink": "https://www.reddit.com/r/managers/comments/item_2/",
            "upvotes": 210,
            "top_comments": []
        },
        {
            "id": "item_3",
            "title": "Sysadmins locked down shadow AI, now legal department is breaking policies",
            "body": "We turned off unapproved web access to ChatGPT. Now legal counsel is using personal phones to upload NDA contracts to public LLMs because our approved enterprise internal bot is too slow.",
            "subreddit": "sysadmin",
            "author": "sysadmin_chief",
            "created_utc": 1700000200,
            "created_date": today,
            "permalink": "https://www.reddit.com/r/sysadmin/comments/item_3/",
            "upvotes": 310,
            "top_comments": [
                {
                    "author": "compliance_officer_x",
                    "body": "When internal IT tools take 45 seconds per prompt response, frontline staff bypass security entirely.",
                    "upvotes": 154,
                    "created_date": today,
                    "permalink": "https://www.reddit.com/r/sysadmin/comments/item_3/comment/c3"
                }
            ]
        },
        {
            "id": "item_fluff",
            "title": "BUY NOW: Download our free enterprise AI whitepaper and webinar",
            "body": "Join our webinar to learn about AGI 2030 and MMLU benchmark scores. Humbled and honored to share this link!",
            "subreddit": "consulting",
            "author": "spammer",
            "created_utc": 1700000300,
            "created_date": today,
            "permalink": "https://www.reddit.com/r/consulting/comments/fluff/",
            "upvotes": 1,
            "top_comments": []
        }
    ]


def test_content_filter(sample_config, mock_gold_standard_items):
    content_filter = ContentFilter(sample_config)
    filtered = content_filter.filter_items(mock_gold_standard_items)

    # Fluff item should be rejected
    assert len(filtered) == 3
    for item in filtered:
        assert item["id"] != "item_fluff"


def test_claude_synthesizer_mock_mode(sample_config, mock_gold_standard_items):
    synthesizer = ClaudeSynthesizer(sample_config)
    report = synthesizer.synthesize(mock_gold_standard_items, mock=True)

    assert isinstance(report, SynthesisReport)
    assert len(report.findings) >= 3

    # Check evidence standards compliance
    for finding in report.findings:
        assert finding.hypothesis_id in ["H1", "H2", "H3", "EMERGING"]
        assert finding.source_url.startswith("https://")
        assert len(finding.verbatim_quote) > 10
        assert len(finding.persona_tag) > 0
        assert len(finding.company_context) > 0


def test_memory_manager_persistence(sample_config):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_file = tf.name

    try:
        memory_manager = MemoryManager(history_file_path=temp_file)

        initial_findings = [
            {
                "hypothesis_id": "H1",
                "pattern_name": "Shadow AI Workarounds",
                "verbatim_quote": "When internal IT tools take 45 seconds...",
                "source_count": 10
            }
        ]

        # First run -> Should be New Pattern
        annotated_1 = memory_manager.process_and_update(initial_findings)
        assert annotated_1[0]["trend_status"] == "New Pattern"
        assert annotated_1[0]["occurrence_count"] == 1

        # Second run with higher source count -> Should be Strengthening
        second_findings = [
            {
                "hypothesis_id": "H1",
                "pattern_name": "Shadow AI Workarounds",
                "verbatim_quote": "When internal IT tools take 45 seconds...",
                "source_count": 60
            }
        ]
        annotated_2 = memory_manager.process_and_update(second_findings)
        assert annotated_2[0]["trend_status"] == "Strengthening"
        assert annotated_2[0]["occurrence_count"] == 2

    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


def test_markdown_builder_formatting(sample_config):
    builder = MarkdownBuilder(sample_config)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    findings = [
        {
            "hypothesis_id": "H1",
            "pattern_name": "Latency Driving Shadow AI",
            "trend_status": "Strengthening",
            "date": today,
            "source_url": "https://www.reddit.com/r/sysadmin/comments/mock_p3/",
            "verbatim_quote": "When internal IT tools take 45 seconds per prompt response, frontline staff bypass security entirely.",
            "persona_tag": "IT Admin",
            "company_context": "Mid-market Enterprise",
            "signal_strength": "High",
            "source_count": 154,
            "executive_takeaway": "Latency drives compliance risks."
        }
    ]

    synthesis_data = {"summary_overview": "Test executive synthesis overview."}

    weekly_md = builder.build_weekly_digest(today, synthesis_data, findings)
    assert "# 🛰️ Trailhead Market Listening Engine" in weekly_md
    assert "| [Latency Driving Shadow AI]" in weekly_md
    assert "📈 Strengthening" in weekly_md
    assert '> "When internal IT tools take 45 seconds per prompt response, frontline staff bypass security entirely."' in weekly_md

    query_md = builder.build_query_brief("AI policy bypass", today, synthesis_data, findings)
    assert "# 🎯 Targeted Intelligence Brief" in query_md
    assert "`AI policy bypass`" in query_md
