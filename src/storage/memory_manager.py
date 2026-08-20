"""
Memory Manager for persistent trend tracking over time (strengthening, steady, fading).
Manages memory/history_store.json to maintain historical momentum of friction patterns.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages reading, updating, and comparing trend snapshots in history_store.json."""

    def __init__(self, history_file_path: str = "memory/history_store.json"):
        self.history_file_path = history_file_path
        self.history_data = self._load_history()

    def _load_history(self) -> Dict[str, Any]:
        """Loads history store JSON file if it exists, otherwise returns default empty store."""
        if os.path.exists(self.history_file_path):
            try:
                with open(self.history_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load history store at {self.history_file_path}: {e}")

        return {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "historical_trends": {}
        }

    def process_and_update(self, current_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compares current findings with history_store.json.
        Annotates each finding with trend status: 'New Pattern', 'Strengthening', 'Steady', or 'Fading'.
        Updates history store on disk.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        historical_trends = self.history_data.get("historical_trends", {})
        annotated_findings = []

        seen_pattern_keys = set()

        for finding in current_findings:
            # Generate a normalized key for matching
            pattern_name = finding.get("pattern_name", "")
            hyp_id = finding.get("hypothesis_id", "")
            key = f"{hyp_id}:{pattern_name.strip().lower()}"
            seen_pattern_keys.add(key)

            if key in historical_trends:
                # Existing pattern
                prev_record = historical_trends[key]
                prev_count = prev_record.get("occurrence_count", 1)
                prev_sources = prev_record.get("last_source_count", 0)
                current_sources = finding.get("source_count", 1)

                if current_sources > prev_sources or current_sources > 50:
                    status = "Strengthening"
                else:
                    status = "Steady"

                # Update record
                historical_trends[key] = {
                    "pattern_name": pattern_name,
                    "hypothesis_id": hyp_id,
                    "first_seen_date": prev_record.get("first_seen_date", today),
                    "last_seen_date": today,
                    "occurrence_count": prev_count + 1,
                    "last_source_count": current_sources,
                    "trend_status": status,
                    "verbatim_quote": finding.get("verbatim_quote")
                }
            else:
                # New pattern
                status = "New Pattern"
                historical_trends[key] = {
                    "pattern_name": pattern_name,
                    "hypothesis_id": hyp_id,
                    "first_seen_date": today,
                    "last_seen_date": today,
                    "occurrence_count": 1,
                    "last_source_count": finding.get("source_count", 1),
                    "trend_status": status,
                    "verbatim_quote": finding.get("verbatim_quote")
                }

            finding_copy = dict(finding)
            finding_copy["trend_status"] = status
            finding_copy["occurrence_count"] = historical_trends[key]["occurrence_count"]
            annotated_findings.append(finding_copy)

        # Identify fading trends (trends present in history but missing in current run)
        for key, record in list(historical_trends.items()):
            if key not in seen_pattern_keys:
                record["trend_status"] = "Fading"

        self.history_data["last_updated"] = today
        self.history_data["historical_trends"] = historical_trends
        self.save_history()

        return annotated_findings

    def save_history(self) -> None:
        """Saves current state to history_store.json file."""
        os.makedirs(os.path.dirname(self.history_file_path), exist_ok=True)
        try:
            with open(self.history_file_path, "w", encoding="utf-8") as f:
                json.dump(self.history_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated memory store saved to {self.history_file_path}")
        except Exception as e:
            logger.error(f"Failed to save history store to {self.history_file_path}: {e}")
