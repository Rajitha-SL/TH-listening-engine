import pytest
from src.processors.claude_synthesizer import ClaudeSynthesizer, EvidenceFinding, _clean_html_text
from src.processors.filter import ContentFilter


def test_clean_html_text():
    raw_html = "<!-- SC_OFF --><div><p>Verbatim quote with <a href='https://example.com'>link</a> &amp; &quot;entities&quot;</p></div><!-- SC_ON -->"
    clean = _clean_html_text(raw_html)
    assert "<!-- SC_OFF -->" not in clean
    assert "<p>" not in clean
    assert "<a>" not in clean
    assert "&amp;" not in clean
    assert 'Verbatim quote with link & "entities"' in clean


def test_negative_filter_rejection():
    config = {
        "negative_filters": {
            "exclude_keywords": ["vendor marketing", "AGI singularity", "Sonnet vs GPT-4", "resume review", "SPHR prep"]
        }
    }
    content_filter = ContentFilter(config)
    items = [
        {"title": "Check out our vendor marketing AI lead-gen tool!", "body": "Best AGI singularity product", "subreddit": "sysadmin"},
        {"title": "Copilot developer friction in legacy codebase", "body": "Devs refuse to use copilot", "subreddit": "ExperiencedDevs"}
    ]
    filtered = content_filter.filter_items(items)
    assert len(filtered) == 1
    assert "Copilot" in filtered[0]["title"]


def test_claude_synthesizer_hypotheses_tags(sample_config):
    synthesizer = ClaudeSynthesizer(sample_config)
    mock_report = synthesizer.synthesize([], query_prompt="Copilot friction", mock=True)
    valid_tags = {"H1", "H2", "H3", "EMERGING"}
    for finding in mock_report.findings:
        assert finding.hypothesis_id in valid_tags
        assert len(finding.verbatim_quote) > 0
        assert "http" in finding.source_url
