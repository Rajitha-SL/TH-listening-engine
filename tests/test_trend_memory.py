import os
import tempfile
import pytest
from src.storage.trend_memory import TrendMemoryStore


@pytest.fixture
def temp_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name
    store = TrendMemoryStore(db_path=temp_db_path)
    yield store
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except Exception:
            pass


def test_trend_memory_init(temp_store):
    history = temp_store.get_run_history()
    assert len(history) == 0


def test_trend_memory_momentum_thresholds(temp_store):
    # First run: new pattern -> Strengthening (+100.0%)
    res1 = temp_store.calculate_trend_momentum("Copilot Developer Friction", current_signal_count=100)
    assert res1["momentum"] == "Strengthening"
    assert res1["is_new"] is True

    # Save run snapshot
    run_meta = {"run_id": "run_test_1", "run_date": "2026-08-23", "mode": "query", "prompt": "Copilot"}
    hypotheses = [{"hypothesis_id": "H1", "pattern_name": "Copilot Developer Friction", "persona_tag": "Dev Lead", "source_count": 100, "trend_status": res1["momentum"], "delta_pct": res1["delta_pct"]}]
    temp_store.save_run_snapshot(run_meta, hypotheses)

    # Second run: count increases by > 15% (100 -> 130) -> Strengthening
    res2 = temp_store.calculate_trend_momentum("Copilot Developer Friction", current_signal_count=130)
    assert res2["momentum"] == "Strengthening"
    assert res2["delta_pct"] == 30.0

    # Save second run snapshot
    run_meta2 = {"run_id": "run_test_2", "run_date": "2026-08-23", "mode": "query", "prompt": "Copilot"}
    hypotheses2 = [{"hypothesis_id": "H1", "pattern_name": "Copilot Developer Friction", "persona_tag": "Dev Lead", "source_count": 130, "trend_status": res2["momentum"], "delta_pct": res2["delta_pct"]}]
    temp_store.save_run_snapshot(run_meta2, hypotheses2)

    # Third run: count decreases by > 15% (130 -> 80) -> Fading
    res3 = temp_store.calculate_trend_momentum("Copilot Developer Friction", current_signal_count=80)
    assert res3["momentum"] == "Fading"
    assert res3["delta_pct"] < 0

    # Fourth run: count within +/- 15% (80 -> 82) -> Steady
    run_meta3 = {"run_id": "run_test_3", "run_date": "2026-08-23", "mode": "query", "prompt": "Copilot"}
    hypotheses3 = [{"hypothesis_id": "H1", "pattern_name": "Copilot Developer Friction", "persona_tag": "Dev Lead", "source_count": 80, "trend_status": res3["momentum"], "delta_pct": res3["delta_pct"]}]
    temp_store.save_run_snapshot(run_meta3, hypotheses3)

    res4 = temp_store.calculate_trend_momentum("Copilot Developer Friction", current_signal_count=82)
    assert res4["momentum"] == "Steady"


def test_trend_memory_clear_cache(temp_store):
    run_meta = {"run_id": "run_clear_test", "run_date": "2026-08-23", "mode": "query", "prompt": "Test"}
    hypotheses = [{"hypothesis_id": "H1", "pattern_name": "Test Pattern", "persona_tag": "Tester", "source_count": 50, "trend_status": "Steady", "delta_pct": 0.0}]
    temp_store.save_run_snapshot(run_meta, hypotheses)

    history_before = temp_store.get_run_history()
    assert len(history_before) == 1

    temp_store.clear_memory_cache()
    history_after = temp_store.get_run_history()
    assert len(history_after) == 0
