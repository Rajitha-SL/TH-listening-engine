"""
Trend Momentum Persistence Store using SQLite.
Tracks historical signal counts, computes cross-run velocity (Strengthening, Steady, Fading),
and persists run snapshots across weekly digests and on-demand queries.
"""

import os
import sqlite3
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("trend_memory")


class TrendMemoryStore:
    """Manages SQLite database for tracking cross-run trend velocity and historical snapshots."""

    def __init__(self, db_path: str = "data/trend_history.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes database schema if tables do not exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT UNIQUE,
                        timestamp REAL,
                        run_date TEXT,
                        mode TEXT,
                        prompt TEXT,
                        evidence_count INTEGER
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS hypotheses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT,
                        hypothesis_id TEXT,
                        name TEXT,
                        persona TEXT,
                        signal_count INTEGER,
                        momentum TEXT,
                        delta_pct REAL,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id)
                    );
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing SQLite trend database at {self.db_path}: {e}")

    def calculate_trend_momentum(
        self, hypothesis_name: str, current_signal_count: int, prompt_topic: str = ""
    ) -> Dict[str, Any]:
        """
        Calculates week-over-week signal delta against historical run baseline.
        Returns dict with momentum status ('Strengthening', 'Steady', 'Fading'), delta_pct, and is_new flag.
        """
        clean_name = hypothesis_name.strip().lower()
        prev_count = None

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Find most recent previous count for semantically matching hypothesis
                cursor.execute("""
                    SELECT h.signal_count 
                    FROM hypotheses h
                    JOIN runs r ON h.run_id = r.run_id
                    WHERE LOWER(h.name) = ? OR LOWER(h.name) LIKE ?
                    ORDER BY r.timestamp DESC
                    LIMIT 1
                """, (clean_name, f"%{clean_name[:20]}%"))
                row = cursor.fetchone()
                if row:
                    prev_count = row["signal_count"]
        except Exception as e:
            logger.warning(f"Error querying historical trend baseline: {e}")

        if prev_count is None or prev_count == 0:
            return {
                "momentum": "Strengthening",
                "delta_pct": 100.0,
                "is_new": True,
                "prev_count": 0
            }

        delta_pct = round(((current_signal_count - prev_count) / max(prev_count, 1)) * 100, 1)

        if current_signal_count >= prev_count * 1.15:
            momentum = "Strengthening"
        elif current_signal_count <= prev_count * 0.85:
            momentum = "Fading"
        else:
            momentum = "Steady"

        return {
            "momentum": momentum,
            "delta_pct": delta_pct,
            "is_new": False,
            "prev_count": prev_count
        }

    def save_run_snapshot(self, run_metadata: Dict[str, Any], hypotheses: List[Dict[str, Any]]) -> str:
        """Saves run metadata and findings snapshot to SQLite store."""
        now_ts = time.time()
        run_id = run_metadata.get("run_id") or f"run_{int(now_ts)}"
        run_date = run_metadata.get("run_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mode = run_metadata.get("mode", "query")
        prompt = run_metadata.get("prompt", "")
        evidence_count = len(hypotheses)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO runs (run_id, timestamp, run_date, mode, prompt, evidence_count)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (run_id, now_ts, run_date, mode, prompt, evidence_count))

                for h in hypotheses:
                    h_id = h.get("hypothesis_id", "H1")
                    h_name = h.get("pattern_name") or h.get("name", "Workplace Pattern")
                    persona = h.get("persona_tag") or h.get("persona", "Practitioner")
                    sig_cnt = h.get("source_count") or h.get("signal_count", 50)
                    momentum = h.get("trend_status") or h.get("momentum", "Strengthening")
                    delta_pct = h.get("delta_pct", 0.0)

                    cursor.execute("""
                        INSERT INTO hypotheses (run_id, hypothesis_id, name, persona, signal_count, momentum, delta_pct)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (run_id, h_id, h_name, persona, sig_cnt, momentum, delta_pct))

                conn.commit()
                logger.info(f"Saved run snapshot {run_id} to trend memory database.")
        except Exception as e:
            logger.error(f"Failed to save run snapshot: {e}")

        return run_id

    def get_run_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves formatted run summaries for GUI display."""
        history = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT run_id, timestamp, run_date, mode, prompt, evidence_count
                    FROM runs
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                for row in rows:
                    history.append({
                        "run_id": row["run_id"],
                        "run_date": row["run_date"],
                        "mode": row["mode"],
                        "prompt": row["prompt"],
                        "evidence_count": row["evidence_count"]
                    })
        except Exception as e:
            logger.error(f"Error fetching run history: {e}")
        return history

    def clear_memory_cache(self) -> None:
        """Clears all historical records and resets database schema."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TABLE IF EXISTS hypotheses;")
                cursor.execute("DROP TABLE IF EXISTS runs;")
                conn.commit()
            self._init_db()
            logger.info("Trend memory database cleared and schema reset.")
        except Exception as e:
            logger.error(f"Error clearing trend memory database: {e}")
