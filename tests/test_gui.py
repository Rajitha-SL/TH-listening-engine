"""
Automated Unit and Integration Test Suite for Desktop GUI & Engine Integration.
"""

import os
import tempfile
import pytest
from datetime import datetime

from gui import update_env_file, EngineArgs, SchedulerManager
from main import run_weekly_mode, run_query_mode, load_config, get_resource_path


@pytest.fixture
def test_env_file():
    with tempfile.NamedTemporaryFile(suffix=".env", mode="w+", delete=False, encoding="utf-8") as tf:
        temp_path = tf.name
        tf.write("EXISTING_KEY=12345\n")
    yield temp_path
    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_update_env_file(test_env_file):
    # Test updating existing key
    update_env_file("EXISTING_KEY", "67890", env_path=test_env_file)
    with open(test_env_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "EXISTING_KEY=67890" in content

    # Test adding new key
    update_env_file("ANTHROPIC_API_KEY", "sk-test-key", env_path=test_env_file)
    with open(test_env_file, "r", encoding="utf-8") as f:
        content_updated = f.read()
    assert "ANTHROPIC_API_KEY=sk-test-key" in content_updated


def test_gui_engine_mock_query_run(sample_config):
    logs = []
    def log_cb(msg):
        logs.append(msg)

    args = EngineArgs(mode="query", prompt="shadow AI workarounds", days=7, mock=True)
    filepath = run_query_mode(sample_config, args, status_callback=log_cb)

    assert os.path.exists(filepath)
    html_filepath = filepath.replace(".md", ".html")
    assert os.path.exists(html_filepath)
    assert len(logs) > 0
    assert any("Starting On-Demand Query Mode" in l for l in logs)


def test_gui_engine_mock_weekly_run(sample_config):
    logs = []
    def log_cb(msg):
        logs.append(msg)

    args = EngineArgs(mode="weekly", days=7, mock=True)
    filepath = run_weekly_mode(sample_config, args, status_callback=log_cb)

    assert os.path.exists(filepath)
    html_filepath = filepath.replace(".md", ".html")
    assert os.path.exists(html_filepath)
    assert len(logs) > 0
    assert any("Starting Weekly Intelligence Digest" in l for l in logs)


def test_scheduler_manager_configuration():
    triggered = []
    def dummy_run():
        triggered.append(True)

    status_updates = []
    def dummy_status(dt):
        status_updates.append(dt)

    manager = SchedulerManager(run_callback=dummy_run, status_update_callback=dummy_status)
    assert manager.enabled is False

    manager.update_schedule("Monday", "14:00")
    assert manager.scheduled_day == "monday"
    assert manager.scheduled_time == "14:00"


def test_gui_config_tab_source_formatting(sample_config):
    # Test formatting with dictionary and string rss_feeds
    rss_feeds = [
        {"name": "Feed 1", "url": "https://example.com/rss1"},
        "https://example.com/rss2"
    ]
    subreddits = ["humanresources", "sysadmin"]

    formatted_subreddits = [f"r/{s}" if isinstance(s, str) else f"r/{s.get('name', str(s))}" for s in subreddits]

    formatted_rss = []
    for feed in rss_feeds:
        if isinstance(feed, dict):
            name = feed.get("name")
            url = feed.get("url")
            if name and url:
                formatted_rss.append(f"{name} ({url})")
            elif name:
                formatted_rss.append(name)
            elif url:
                formatted_rss.append(url)
        elif isinstance(feed, str):
            formatted_rss.append(feed)
        else:
            formatted_rss.append(str(feed))

    sources_text = f"Subreddits ({len(subreddits)}):\n  " + (", ".join(formatted_subreddits) if formatted_subreddits else "None configured") + "\n\n"
    sources_text += f"RSS Feeds ({len(rss_feeds)}):\n  " + ("\n  ".join(formatted_rss) if formatted_rss else "None configured")

    assert "r/humanresources" in sources_text
    assert "Feed 1 (https://example.com/rss1)" in sources_text
    assert "https://example.com/rss2" in sources_text

