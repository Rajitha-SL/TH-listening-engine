import pytest

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
