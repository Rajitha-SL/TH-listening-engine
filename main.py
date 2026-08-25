"""
Main CLI Entrypoint for Trailhead Market Listening Engine.
Supports Automated Weekly Mode (--mode weekly) and On-Demand Targeted Query Mode (--mode query --prompt "...").
"""

import sys
import os
import yaml
import argparse
import logging
import webbrowser
from datetime import datetime, timezone
from typing import Dict, Any

from src.collectors.reddit_collector import RedditCollector
from src.collectors.web_collector import WebCollector
from src.collectors.public_web_collector import PublicWebCollector
from src.processors.filter import ContentFilter
from src.processors.claude_synthesizer import ClaudeSynthesizer
from src.storage.memory_manager import MemoryManager
from src.formatters.markdown_builder import MarkdownBuilder
from src.formatters.html_builder import HTMLBuilder
from dotenv import load_dotenv

load_dotenv()

# Configure logging
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("main")


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(getattr(sys, '_MEIPASS'), relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class GUIStatusHandler(logging.Handler):
    """Custom logging handler to route log messages to GUI callback."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            msg = self.format(record)
            if self.callback:
                self.callback(msg)
        except Exception:
            pass


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Loads configuration YAML file with PyInstaller resource path fallback."""
    target_path = config_path
    if not os.path.exists(target_path):
        fallback_path = get_resource_path(config_path)
        if os.path.exists(fallback_path):
            target_path = fallback_path

    if not os.path.exists(target_path):
        logger.warning(f"Config file '{config_path}' not found. Using empty defaults.")
        return {}
    with open(target_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_weekly_mode(config: Dict[str, Any], args: Any, status_callback=None) -> str:
    """Executes automated weekly intelligence digest workflow."""
    gui_handler = None
    if status_callback:
        gui_handler = GUIStatusHandler(status_callback)
        gui_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
        logging.getLogger().addHandler(gui_handler)

    try:
        logger.info("--- Starting Weekly Intelligence Digest Ingestion ---")
        if status_callback:
            status_callback("--- Starting Weekly Intelligence Digest Ingestion ---")
        
        # Standardized 24-hour timestamp format (YYYY_MM_DD_HHMM)
        timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M")
        report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        subreddits = config.get("target_sources", {}).get("subreddits", [])
        rss_feeds = config.get("target_sources", {}).get("rss_feeds", [])
        keywords = config.get("search_keywords", [])
        
        days_lookback = getattr(args, 'days', None) or config.get("parameters", {}).get("default_days_lookback", 7)
        limit = getattr(args, 'limit', None) or getattr(args, 'article_limit', None) or 5
        mock_mode = getattr(args, 'mock', False)
        history_path = getattr(args, 'history', 'memory/history_store.json')
        output_dir = getattr(args, 'output_dir', 'output')

        # 1. Collect raw data
        reddit_collector = RedditCollector(config)
        raw_reddit = reddit_collector.fetch_subreddit_posts(
            subreddits=subreddits,
            keywords=keywords,
            days_lookback=days_lookback,
            mock=mock_mode
        )

        web_collector = WebCollector()
        raw_web = web_collector.fetch_rss_feeds(
            rss_sources=rss_feeds,
            keywords=keywords,
            days_lookback=days_lookback,
            mock=mock_mode
        )

        raw_items = raw_reddit + raw_web
        logger.info(f"Total raw items collected: {len(raw_items)}")

        # 2. Pre-filter noise & fluff
        content_filter = ContentFilter(config)
        filtered_items = content_filter.filter_items(raw_items)

        # 3. Synthesize findings via Claude
        synthesizer = ClaudeSynthesizer(config)
        synthesis_report = synthesizer.synthesize(filtered_items, mock=mock_mode, limit=limit)
        report_dict = synthesis_report.model_dump()

        # 4. Process trend memory & track momentum
        memory_manager = MemoryManager(history_file_path=history_path)
        annotated_findings = memory_manager.process_and_update(report_dict.get("findings", []))

        # 5. Build Markdown & HTML digests
        builder = MarkdownBuilder(config)
        markdown_output = builder.build_weekly_digest(
            report_date=report_date,
            synthesis_data=report_dict,
            findings=annotated_findings
        )

        html_builder = HTMLBuilder(config)
        html_output = html_builder.build_weekly_html(
            report_date=report_date,
            synthesis_data=report_dict,
            findings=annotated_findings,
            limit=limit
        )

        # 6. Save dual timestamped output files (.md and .html)
        os.makedirs(output_dir, exist_ok=True)
        digest_filename = f"digest_{timestamp}.md"
        digest_filepath = os.path.join(output_dir, digest_filename)
        html_filename = f"digest_{timestamp}.html"
        html_filepath = os.path.join(output_dir, html_filename)

        with open(digest_filepath, "w", encoding="utf-8") as f:
            f.write(markdown_output)

        with open(html_filepath, "w", encoding="utf-8") as f:
            f.write(html_output)

        logger.info(f"Successfully generated weekly digest: {digest_filepath} & {html_filepath}")

        # 7. Auto-open interactive HTML report in default browser
        try:
            webbrowser.open(os.path.abspath(html_filepath))
        except Exception as e:
            logger.warning(f"Could not auto-open HTML report in browser: {e}")

        return digest_filepath
    finally:
        if gui_handler:
            logging.getLogger().removeHandler(gui_handler)



def run_query_mode(config: Dict[str, Any], args: Any, status_callback=None) -> str:
    """Executes on-demand targeted query workflow."""
    prompt_str = getattr(args, 'prompt', None)
    if not prompt_str:
        logger.error("Error: prompt argument is required in 'query' mode.")
        if status_callback:
            status_callback("Error: prompt argument is required in 'query' mode.")
        if __name__ == "__main__":
            sys.exit(1)
        raise ValueError("Prompt argument is required in query mode.")

    gui_handler = None
    if status_callback:
        gui_handler = GUIStatusHandler(status_callback)
        gui_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
        logging.getLogger().addHandler(gui_handler)

    try:
        logger.info(f"--- Starting On-Demand Query Mode: '{prompt_str}' ---")
        if status_callback:
            status_callback(f"--- Starting On-Demand Query Mode: '{prompt_str}' ---")
        
        # Standardized 24-hour timestamp format (YYYY_MM_DD_HHMM)
        timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M")
        report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        subreddits = config.get("target_sources", {}).get("subreddits", [])
        rss_feeds = config.get("target_sources", {}).get("rss_feeds", [])
        days_lookback = getattr(args, 'days', None) or config.get("parameters", {}).get("default_days_lookback", 14)
        limit = getattr(args, 'limit', None) or getattr(args, 'article_limit', None) or 5
        mock_mode = getattr(args, 'mock', False)
        output_dir = getattr(args, 'output_dir', 'output')

        # 1. Ingest
        reddit_collector = RedditCollector(config)
        raw_reddit = reddit_collector.search_posts(
            query=prompt_str,
            subreddits=subreddits,
            lookback_days=days_lookback,
            limit=limit,
            mock=mock_mode
        )

        query_keywords = [w.strip() for w in prompt_str.split() if len(w.strip()) > 3]
        web_collector = WebCollector()
        raw_web = web_collector.fetch_rss_feeds(
            rss_sources=rss_feeds,
            keywords=query_keywords,
            days_lookback=days_lookback,
            mock=mock_mode
        )

        public_web_collector = PublicWebCollector(config)
        raw_mirrors = public_web_collector.fetch_blind_fishbowl_mirrors(prompt_str, lookback_days=days_lookback, mock=mock_mode)
        raw_jobs = public_web_collector.fetch_ai_job_transformation_signals(prompt_str, lookback_days=days_lookback, mock=mock_mode)

        raw_items = raw_reddit + raw_web + raw_mirrors + raw_jobs

        # 2. Filter
        content_filter = ContentFilter(config)
        filtered_items = content_filter.filter_items(raw_items)

        # 3. Synthesize targeted report
        synthesizer = ClaudeSynthesizer(config)
        synthesis_report = synthesizer.synthesize(filtered_items, query_prompt=prompt_str, mock=mock_mode, limit=limit)
        report_dict = synthesis_report.model_dump()

        # 4. Build targeted Markdown brief & HTML report
        builder = MarkdownBuilder(config)
        markdown_output = builder.build_query_brief(
            query_prompt=prompt_str,
            report_date=report_date,
            synthesis_data=report_dict,
            findings=report_dict.get("findings", [])
        )

        html_builder = HTMLBuilder(config)
        html_output = html_builder.build_query_html(
            query_prompt=prompt_str,
            report_date=report_date,
            synthesis_data=report_dict,
            findings=report_dict.get("findings", []),
            limit=limit
        )

        # Print to stdout safely
        print("\n" + "=" * 80)
        try:
            print(markdown_output)
        except UnicodeEncodeError:
            print(markdown_output.encode("ascii", errors="backslashreplace").decode("ascii"))
        print("=" * 80 + "\n")

        # 5. Save dual timestamped output files (.md and .html)
        os.makedirs(output_dir, exist_ok=True)
        query_filename = f"query_{timestamp}.md"
        query_filepath = os.path.join(output_dir, query_filename)
        html_filename = f"query_{timestamp}.html"
        html_filepath = os.path.join(output_dir, html_filename)

        with open(query_filepath, "w", encoding="utf-8") as f:
            f.write(markdown_output)

        with open(html_filepath, "w", encoding="utf-8") as f:
            f.write(html_output)

        logger.info(f"Targeted query brief saved to: {query_filepath} & {html_filepath}")

        # 6. Auto-open interactive HTML report in default browser
        try:
            webbrowser.open(os.path.abspath(html_filepath))
        except Exception as e:
            logger.warning(f"Could not auto-open HTML report in browser: {e}")

        return query_filepath
    finally:
        if gui_handler:
            logging.getLogger().removeHandler(gui_handler)


def main():
    parser = argparse.ArgumentParser(
        description="Trailhead Market Listening Engine - Enterprise AI Adoption Research Tool"
    )
    parser.add_argument(
        "--mode",
        choices=["weekly", "query"],
        default="weekly",
        help="Execution mode: 'weekly' (automated weekly digest) or 'query' (on-demand targeted brief)."
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Targeted prompt query string (required in query mode)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file."
    )
    parser.add_argument(
        "--history",
        type=str,
        default="memory/history_store.json",
        help="Path to JSON trend memory store."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save output markdown files."
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Override lookback period in days."
    )
    parser.add_argument(
        "--limit", "--article-limit",
        type=int,
        default=5,
        help="Target number of top evidence articles to synthesize and display (5 to 12)."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in dry-run mock mode without invoking external APIs."
    )

    args = parser.parse_args()

    config = load_config(args.config)

    if args.mode == "weekly":
        output_path = run_weekly_mode(config, args)
        print(f"Digest generated successfully: {output_path}")
    elif args.mode == "query":
        output_path = run_query_mode(config, args)
        print(f"Query brief generated successfully: {output_path}")


if __name__ == "__main__":
    main()