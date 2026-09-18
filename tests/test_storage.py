"""Tests para storage (SQLite)."""

from pathlib import Path

import pytest

from src.storage import (
    close_position,
    get_closed_positions,
    get_open_positions,
    get_recent_analyses,
    get_seen_tokens,
    get_stats,
    get_today_realized_loss,
    init_db,
    mark_seen,
    save_analysis,
    save_position,
    update_position_state,
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
        "analysis": {
            "score": 45,
            "details": [{"filter": "mc", "points": 20, "reason": "ok"}],
        },
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
        save_analysis(
            {
                "token": {"token_address": f"TOK{i}", "symbol": f"T{i}"},
                "analysis": {"score": i * 10, "details": []},
                "ai": {"score": i * 5, "reason": "test"},
                "final_score": i * 8,
                "action": "EVITAR",
                "executed": False,
            },
            temp_db,
        )

    rows = get_recent_analyses(limit=10, db_path=temp_db)
    assert len(rows) == 3
    assert rows[0]["symbol"] == "T2"  # el más reciente primero


def test_get_stats_counts_actions(temp_db):
    """Estadísticas por acción."""
    init_db(temp_db)
    for action in ["COMPRA", "COMPRA", "EVITAR", "OBSERVAR"]:
        save_analysis(
            {
                "token": {"token_address": "T", "symbol": "S"},
                "analysis": {"score": 50, "details": []},
                "ai": {"score": 50, "reason": ""},
                "final_score": 50,
                "action": action,
                "executed": action == "COMPRA",
            },
            temp_db,
        )

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


# ============ seen_tokens ============


def test_mark_seen_and_get(temp_db):
    """mark_seen persiste y get_seen_tokens lo recupera."""
    init_db(temp_db)
    mark_seen("TOK1", temp_db)
    mark_seen("TOK2", temp_db)
    mark_seen("TOK1", temp_db)  # idempotente

    seen = get_seen_tokens(temp_db)
    assert seen == {"TOK1", "TOK2"}


def test_get_seen_tokens_empty(temp_db):
    """Sin tokens marcados → set vacío."""
    init_db(temp_db)
    assert get_seen_tokens(temp_db) == set()


# ============ posiciones ============


def _position(token: str = "TOK1", symbol: str = "TEST", entry: float = 0.001):
    return {
        "token_address": token,
        "symbol": symbol,
        "entry_price": entry,
        "amount_sol": 0.03,
        "tp_price": entry * 1.2,
        "sl_price": entry * 0.9,
    }


def test_save_and_get_open_positions(temp_db):
    """save_position inserta una posición abierta recuperable."""
    init_db(temp_db)
    save_position(_position(), temp_db)

    open_positions = get_open_positions(temp_db)
    assert len(open_positions) == 1
    row = open_positions[0]
    assert row["token_address"] == "TOK1"
    assert row["status"] == "open"
    assert row["tp_price"] == pytest.approx(0.0012)
    assert row["max_price_reached"] == pytest.approx(0.001)


def test_close_position_marks_closed(temp_db):
    """close_position actualiza exit_price, pnl y status."""
    init_db(temp_db)
    save_position(_position(), temp_db)

    assert close_position("TOK1", exit_price=0.0015, pnl_sol=-0.005, db_path=temp_db)
    assert get_open_positions(temp_db) == []
    closed_rows = close_position("TOK1", 0.0, 0.0, db_path=temp_db)  # idempotente
    assert closed_rows is False


def test_get_closed_positions_history(temp_db):
    """get_closed_positions devuelve cerradas ordenadas por cierre desc."""
    init_db(temp_db)
    save_position(_position("TOK1", "PRIMERA"), temp_db)
    save_position(_position("TOK2", "SEGUNDA"), temp_db)
    close_position("TOK1", exit_price=0.0015, pnl_sol=0.002, db_path=temp_db)
    close_position("TOK2", exit_price=0.0009, pnl_sol=-0.003, db_path=temp_db)

    closed = get_closed_positions(limit=10, db_path=temp_db)
    assert len(closed) == 2
    assert closed[0]["symbol"] == "SEGUNDA"  # más reciente primero
    assert closed[0]["pnl_sol"] == pytest.approx(-0.003)
    assert closed[1]["symbol"] == "PRIMERA"
    assert {p["status"] for p in closed} == {"closed"}


def test_update_position_state_trailing(temp_db):
    """update_position_state persiste el nuevo SL/trailing."""
    init_db(temp_db)
    save_position(_position(), temp_db)

    assert update_position_state(
        "TOK1",
        sl_price=0.0011,
        trailing_active=True,
        max_price_reached=0.0012,
        db_path=temp_db,
    )
    rows = get_open_positions(temp_db)
    assert rows[0]["sl_price"] == pytest.approx(0.0011)
    assert rows[0]["trailing_active"] == 1
    assert rows[0]["max_price_reached"] == pytest.approx(0.0012)


def test_get_today_realized_loss(temp_db):
    """Suma solo las pérdidas del día (pnl negativo, cerradas)."""
    init_db(temp_db)
    save_position(_position("A"), temp_db)
    save_position(_position("B"), temp_db)
    save_position(_position("C"), temp_db)

    close_position("A", exit_price=0.0009, pnl_sol=-0.01, db_path=temp_db)
    close_position("B", exit_price=0.0011, pnl_sol=0.02, db_path=temp_db)
    close_position("C", exit_price=0.0008, pnl_sol=-0.03, db_path=temp_db)

    assert get_today_realized_loss(temp_db) == pytest.approx(-0.04)


def test_open_position_does_not_load_schema_default(temp_db):
    """Migración: DB creada con schema viejo gana las nuevas columnas."""
    init_db(temp_db)
    save_position(_position(), temp_db)
    rows = get_open_positions(temp_db)
    assert "tp_price" in rows[0]
