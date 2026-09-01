"""
URL and fetch safety helpers.

Report links and outbound collector URLs must be public HTTPS only.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Iterable, Optional
from urllib.parse import urlparse

DEFAULT_FALLBACK_URL = "https://www.reddit.com/search/?q=enterprise+AI"

ALLOWED_REPORT_HOST_SUFFIXES = (
    "reddit.com",
    "remoteok.com",
    "weworkremotely.com",
    "greenhouse.io",
    "lever.co",
    "indeed.com",
    "news.ycombinator.com",
    "teamblind.com",
    "fishbowlapp.com",
    "duckduckgo.com",
    "news.google.com",
    "google.com",
)

_BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata.google.com",
    "169.254.169.254",
}

_BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost")
_SAFE_SUBREDDIT = re.compile(r"^[A-Za-z0-9_]+$")


def is_safe_subreddit_name(name: str) -> bool:
    """True when a subreddit token cannot alter the Reddit request path."""
    if not name or not isinstance(name, str):
        return False
    token = name.strip().strip("/")
    if token.lower().startswith("r/"):
        token = token[2:]
    return bool(_SAFE_SUBREDDIT.fullmatch(token))


def _hostname(parsed) -> str:
    return (parsed.hostname or "").lower().rstrip(".")


def _is_blocked_host(host: str) -> bool:
    if not host or host in _BLOCKED_HOSTS:
        return True
    if any(host.endswith(sfx) for sfx in _BLOCKED_HOST_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return bool(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return False


def _host_allowed(host: str, suffixes: Iterable[str]) -> bool:
    return any(host == sfx or host.endswith("." + sfx) for sfx in suffixes)


def is_public_https_url(raw_url: Optional[str]) -> bool:
    """True when the URL is https, has no credentials, and is not a local/private target."""
    if not raw_url or not isinstance(raw_url, str):
        return False
    url = raw_url.strip()
    if not url or url.lower().startswith(("javascript:", "data:", "file:", "vbscript:")):
        return False
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        return False
    if parsed.username or parsed.password:
        return False
    host = _hostname(parsed)
    if _is_blocked_host(host):
        return False
    if parsed.port not in (None, 443):
        return False
    return True


def is_allowed_fetch_url(raw_url: Optional[str]) -> bool:
    """Gate for collector outbound fetches (RSS, APIs)."""
    return is_public_https_url(raw_url)


def sanitize_public_https_url(
    raw_url: Optional[str],
    fallback: str = DEFAULT_FALLBACK_URL,
    allowed_suffixes: Iterable[str] = ALLOWED_REPORT_HOST_SUFFIXES,
) -> str:
    """
    Normalize a source URL for embedding in HTML/Markdown reports.

    Relative Reddit paths are expanded. Non-https, local, or unknown hosts
    are replaced with the fallback search URL.
    """
    if not raw_url or not isinstance(raw_url, str):
        return fallback
    url = raw_url.strip()
    if not url or url == "#":
        return fallback

    lowered = url.lower()
    if lowered.startswith(("javascript:", "data:", "file:", "vbscript:", "http://")):
        return fallback

    if not lowered.startswith("https://"):
        if url.startswith("/"):
            url = f"https://www.reddit.com{url}"
        elif url.startswith("r/"):
            url = f"https://www.reddit.com/{url}"
        elif lowered.startswith("www.reddit.com") or lowered.startswith("reddit.com"):
            url = f"https://{url.lstrip('/')}" if not lowered.startswith("https://") else url
            if not url.lower().startswith("https://"):
                url = f"https://{url}"
        else:
            return fallback

    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        return fallback
    host = _hostname(parsed)
    if _is_blocked_host(host) or parsed.username or parsed.password:
        return fallback
    if not _host_allowed(host, allowed_suffixes):
        return fallback
    return url


def markdown_link_label(text: str) -> str:
    """Neutralize Markdown link and table injection in visible labels."""
    cleaned = (text or "").replace("\r", " ").replace("\n", " ")
    for ch in ("[", "]", "(", ")", "|", "`"):
        cleaned = cleaned.replace(ch, " ")
    return " ".join(cleaned.split())


def markdown_href(raw_url: Optional[str]) -> str:
    """Return a report-safe HTTPS URL with parentheses encoded for Markdown links."""
    safe = sanitize_public_https_url(raw_url)
    return safe.replace("(", "%28").replace(")", "%29").replace(" ", "%20")
