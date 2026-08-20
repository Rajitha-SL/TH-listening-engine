"""
Main CLI Entrypoint for Trailhead Market Listening Engine.
Supports Automated Weekly Mode (--mode weekly) and On-Demand Targeted Query Mode (--mode query --prompt "...").
"""

import sys
import os
import yaml
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from src.collectors.reddit_collector import RedditCollector
from src.collectors.web_collector import WebCollector
from src.processors.filter import ContentFilter
from src.processors.claude_synthesizer import ClaudeSynthesizer
from src.storage.memory_manager import MemoryManager
from src.formatters.markdown_builder import MarkdownBuilder
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


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Loads configuration YAML file."""
    if not os.path.exists(config_path):
        logger.warning(f"Config file '{config_path}' not found. Using empty defaults.")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_weekly_mode(config: Dict[str, Any], args: argparse.Namespace) -> str:
    """Executes automated weekly intelligence digest workflow."""
    logger.info("--- Starting Weekly Intelligence Digest Ingestion ---")
    
    # Accurate execution timestamp including hours, minutes, and seconds
    timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    subreddits = config.get("target_sources", {}).get("subreddits", [])
    rss_feeds = config.get("target_sources", {}).get("rss_feeds", [])
    keywords = config.get("search_keywords", [])
    days_lookback = args.days or config.get("parameters", {}).get("default_days_lookback", 7)

    # 1. Collect raw data
    reddit_collector = RedditCollector(config)
    raw_reddit = reddit_collector.fetch_subreddit_posts(
        subreddits=subreddits,
        keywords=keywords,
        days_lookback=days_lookback,
        mock=args.mock
    )

    web_collector = WebCollector()
    raw_web = web_collector.fetch_rss_feeds(
        rss_sources=rss_feeds,
        keywords=keywords,
        days_lookback=days_lookback,
        mock=args.mock
    )

    raw_items = raw_reddit + raw_web
    logger.info(f"Total raw items collected: {len(raw_items)}")

    # 2. Pre-filter noise & fluff
    content_filter = ContentFilter(config)
    filtered_items = content_filter.filter_items(raw_items)

    # 3. Synthesize findings via Claude
    synthesizer = ClaudeSynthesizer(config)
    synthesis_report = synthesizer.synthesize(filtered_items, mock=args.mock)
    report_dict = synthesis_report.model_dump()

    # 4. Process trend memory & track momentum
    memory_manager = MemoryManager(history_file_path=args.history)
    annotated_findings = memory_manager.process_and_update(report_dict.get("findings", []))

    # 5. Build Markdown digest
    builder = MarkdownBuilder(config)
    markdown_output = builder.build_weekly_digest(
        report_date=report_date,
        synthesis_data=report_dict,
        findings=annotated_findings
    )

    # 6. Save to unique timestamped output file
    os.makedirs(args.output_dir, exist_ok=True)
    digest_filename = f"digest_{timestamp}.md"
    digest_filepath = os.path.join(args.output_dir, digest_filename)

    with open(digest_filepath, "w", encoding="utf-8") as f:
        f.write(markdown_output)

    logger.info(f"Successfully generated weekly digest: {digest_filepath}")
    return digest_filepath


def run_query_mode(config: Dict[str, Any], args: argparse.Namespace) -> str:
    """Executes on-demand targeted query workflow."""
    if not args.prompt:
        logger.error("Error: --prompt argument is required in 'query' mode.")
        sys.exit(1)

    logger.info(f"--- Starting On-Demand Query Mode: '{args.prompt}' ---")
    
    # Accurate execution timestamp including hours, minutes, and seconds
    timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    subreddits = config.get("target_sources", {}).get("subreddits", [])
    rss_feeds = config.get("target_sources", {}).get("rss_feeds", [])
    days_lookback = args.days or config.get("parameters", {}).get("default_days_lookback", 14)

    # Convert prompt words into search keywords
    query_keywords = [w.strip() for w in args.prompt.split() if len(w.strip()) > 3]

    # 1. Ingest
    reddit_collector = RedditCollector(config)
    raw_reddit = reddit_collector.fetch_subreddit_posts(
        subreddits=subreddits,
        keywords=query_keywords,
        days_lookback=days_lookback,
        mock=args.mock
    )

    web_collector = WebCollector()
    raw_web = web_collector.fetch_rss_feeds(
        rss_sources=rss_feeds,
        keywords=query_keywords,
        days_lookback=days_lookback,
        mock=args.mock
    )

    raw_items = raw_reddit + raw_web

    # 2. Filter
    content_filter = ContentFilter(config)
    filtered_items = content_filter.filter_items(raw_items)

    # 3. Synthesize targeted report
    synthesizer = ClaudeSynthesizer(config)
    synthesis_report = synthesizer.synthesize(filtered_items, query_prompt=args.prompt, mock=args.mock)
    report_dict = synthesis_report.model_dump()

    # 4. Build targeted Markdown brief
    builder = MarkdownBuilder(config)
    markdown_output = builder.build_query_brief(
        query_prompt=args.prompt,
        report_date=report_date,
        synthesis_data=report_dict,
        findings=report_dict.get("findings", [])
    )

    # Print to stdout safely
    print("\n" + "=" * 80)
    try:
        print(markdown_output)
    except UnicodeEncodeError:
        print(markdown_output.encode("ascii", errors="backslashreplace").decode("ascii"))
    print("=" * 80 + "\n")

    # 5. Save to unique timestamped output file
    os.makedirs(args.output_dir, exist_ok=True)
    query_filename = f"query_{timestamp}.md"
    query_filepath = os.path.join(args.output_dir, query_filename)

    with open(query_filepath, "w", encoding="utf-8") as f:
        f.write(markdown_output)

    logger.info(f"Targeted query brief saved to: {query_filepath}")
    return query_filepath


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