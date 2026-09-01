"""Tests for public HTTPS URL sanitization and Markdown link escaping."""

from src.net_safety import (
    DEFAULT_FALLBACK_URL,
    is_allowed_fetch_url,
    is_safe_subreddit_name,
    markdown_href,
    markdown_link_label,
    sanitize_public_https_url,
)


def test_sanitize_allows_https_reddit():
    url = "https://www.reddit.com/r/sysadmin/comments/abc/"
    assert sanitize_public_https_url(url) == url


def test_sanitize_rejects_javascript_and_data():
    assert sanitize_public_https_url("javascript:alert(1)") == DEFAULT_FALLBACK_URL
    assert sanitize_public_https_url("DATA:text/html,hi") == DEFAULT_FALLBACK_URL
    assert sanitize_public_https_url("file:///etc/passwd") == DEFAULT_FALLBACK_URL


def test_sanitize_rejects_http_and_unknown_hosts():
    assert sanitize_public_https_url("http://www.reddit.com/r/x") == DEFAULT_FALLBACK_URL
    assert sanitize_public_https_url("https://evil.example/phish") == DEFAULT_FALLBACK_URL
    assert sanitize_public_https_url("https://127.0.0.1/") == DEFAULT_FALLBACK_URL


def test_sanitize_expands_reddit_relative_paths():
    assert sanitize_public_https_url("/r/sysadmin/comments/abc/") == (
        "https://www.reddit.com/r/sysadmin/comments/abc/"
    )


def test_fetch_url_rejects_file_and_localhost():
    assert is_allowed_fetch_url("https://news.google.com/rss") is True
    assert is_allowed_fetch_url("file:///tmp/x.xml") is False
    assert is_allowed_fetch_url("https://localhost/rss") is False
    assert is_allowed_fetch_url("http://news.google.com/rss") is False


def test_safe_subreddit_name():
    assert is_safe_subreddit_name("sysadmin") is True
    assert is_safe_subreddit_name("r/sysadmin") is True
    assert is_safe_subreddit_name("foo/../../evil") is False
    assert is_safe_subreddit_name("sysadmin?q=1") is False


def test_markdown_escaping():
    label = markdown_link_label("x](https://evil.com)[y")
    assert "](" not in label
    assert "https://evil.com" not in markdown_link_label("ok")
    href = markdown_href("javascript:alert(1)")
    assert href.startswith("https://")
    assert "javascript:" not in href.lower()
