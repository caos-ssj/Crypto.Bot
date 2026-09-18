"""Tests para storage (SQLite)."""

from pathlib import Path

import pytest

from src.storage import (
    get_detection,
    get_recent_analyses,
    get_stats,
    init_db,
    mark_detection_processed,
    register_detection,
    save_analysis,
    save_execution,
)


@pytest.fixture
def temp_db(tmp_path):
    """DB temporal para cada test."""
    return str(tmp_path / "test.db")


def test_init_db_creates_file(temp_db):
    """init_db crea el archivo."""
    init_db(temp_db)
    assert Path(temp_db).exists()


def test_save_analysis_inserts_row(temp_db):
    """save_analysis inserta un registro."""
    init_db(temp_db)
    result = {
        "token": {
            "token_address": "TOK1",
            "symbol": "TEST",
            "price_usd": 0.001,
            "market_cap": 50000,
            "liquidity_usd": 5000,
            "volume_5min": 3000,
        },
        "analysis": {"score": 45, "details": [{"filter": "mc", "points": 20, "reason": "ok"}]},
        "ai": {"score": 60, "reason": "Token con buena pinta"},
        "final_score": 50,
        "action": "OBSERVAR",
        "executed": False,
    }
    row_id = save_analysis(result, temp_db)
    assert row_id > 0


def test_get_recent_analyses(temp_db):
    """Recupera análisis guardados."""
    init_db(temp_db)
    for i in range(3):
        save_analysis({
            "token": {"token_address": f"TOK{i}", "symbol": f"T{i}"},
            "analysis": {"score": i * 10, "details": []},
            "ai": {"score": i * 5, "reason": "test"},
            "final_score": i * 8,
            "action": "EVITAR",
            "executed": False,
        }, temp_db)
    
    rows = get_recent_analyses(limit=10, db_path=temp_db)
    assert len(rows) == 3
    assert rows[0]["symbol"] == "T2"  # el más reciente primero


def test_get_stats_counts_actions(temp_db):
    """Estadísticas por acción."""
    init_db(temp_db)
    for action in ["COMPRA", "COMPRA", "EVITAR", "OBSERVAR"]:
        save_analysis({
            "token": {"token_address": "T", "symbol": "S"},
            "analysis": {"score": 50, "details": []},
            "ai": {"score": 50, "reason": ""},
            "final_score": 50,
            "action": action,
            "executed": action == "COMPRA",
        }, temp_db)
    
    stats = get_stats(temp_db)
    assert stats["total"] == 4
    assert stats["compra"] == 2
    assert stats["evitar"] == 1
    assert stats["observar"] == 1
    assert stats["executed"] == 2


def test_get_stats_empty_db(temp_db):
    """DB vacía → todo en 0."""
    init_db(temp_db)
    stats = get_stats(temp_db)
    assert stats["total"] == 0
    assert stats["compra"] == 0

def test_detection_persists_across_calls(temp_db):
    init_db(temp_db)
    assert register_detection("TOKEN-A", temp_db) is True
    assert register_detection("TOKEN-A", temp_db) is False

    detection = get_detection("TOKEN-A", temp_db)
    assert detection is not None
    assert detection["status"] == "DETECTED"

    mark_detection_processed("TOKEN-A", db_path=temp_db)
    detection = get_detection("TOKEN-A", temp_db)
    assert detection["status"] == "PROCESSED"
    assert detection["processed_at"] is not None


def test_execution_is_idempotent(temp_db):
    init_db(temp_db)
    execution = {
        "execution_id": "exec-1",
        "signal_id": "signal-1",
        "token_address": "TOKEN-A",
        "mode": "DRY_RUN",
        "status": "dry_run",
        "amount_sol": 0.01,
        "reason": None,
    }
    save_execution(execution, temp_db)
    execution["status"] = "success"
    execution["transaction_signature"] = "SIG-1"
    save_execution(execution, temp_db)

    from src.storage import _connect
    with _connect(temp_db) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count, status, transaction_signature FROM executions WHERE execution_id = ?",
            ("exec-1",),
        ).fetchone()

    assert row["count"] == 1
    assert row["status"] == "success"
    assert row["transaction_signature"] == "SIG-1"
