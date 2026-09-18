"""Persistencia de análisis en SQLite."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

DEFAULT_DB_PATH = "logs/bot.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    token_address TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price_usd REAL,
    market_cap REAL,
    liquidity_usd REAL,
    volume_5min REAL,
    rule_score INTEGER,
    ai_score INTEGER,
    final_score INTEGER,
    action TEXT,
    executed INTEGER DEFAULT 0,
    ai_reason TEXT,
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON analyses(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_action ON analyses(action);
CREATE INDEX IF NOT EXISTS idx_token ON analyses(token_address);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    token_address TEXT NOT NULL,
    symbol TEXT,
    entry_price REAL,
    exit_price REAL,
    amount_sol REAL,
    pnl_sol REAL,
    tp_price REAL,
    sl_price REAL,
    trailing_active INTEGER DEFAULT 0,
    max_price_reached REAL,
    status TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS seen_tokens (
    token_address TEXT PRIMARY KEY,
    seen_at TEXT NOT NULL
);
"""


def _connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Crea conexión a SQLite y garantiza schema."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.executescript(SCHEMA)

    _COLUMNS = {
        "positions": (
            "tp_price",
            "sl_price",
            "trailing_active",
            "max_price_reached",
        ),
    }
    for table, columns in _COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column in columns:
            if column not in existing:
                # ALTER no soporta IF NOT EXISTS; migración idempotente vía PRAGMA.
                col_type = "INTEGER DEFAULT 0" if "active" in column else "REAL"
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Inicializa la base de datos."""
    with _connect(db_path):
        pass
    logger.info(f"DB inicializada en {db_path}")


def save_analysis(
    result: dict[str, Any],
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Guarda un análisis en la DB.

    Args:
        result: Dict retornado por process_token.
        db_path: Ruta a SQLite.

    Returns:
        ID del registro insertado.
    """
    token = result.get("token", {})
    analysis = result.get("analysis", {})
    ai = result.get("ai", {})

    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO analyses (
                timestamp, token_address, symbol, price_usd, market_cap,
                liquidity_usd, volume_5min, rule_score, ai_score,
                final_score, action, executed, ai_reason, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                token.get("token_address", ""),
                token.get("symbol", "?"),
                token.get("price_usd", 0.0),
                token.get("market_cap", 0.0),
                token.get("liquidity_usd", 0.0),
                token.get("volume_5min", 0.0),
                analysis.get("score", 0),
                ai.get("score", 0),
                result.get("final_score", 0),
                result.get("action", "EVITAR"),
                1 if result.get("executed") else 0,
                ai.get("reason", ""),
                json.dumps(analysis.get("details", []), ensure_ascii=False),
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0
    finally:
        conn.close()


def get_recent_analyses(
    limit: int = 100,
    db_path: str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """Obtiene los análisis más recientes.

    Args:
        limit: Máximo de registros.
        db_path: Ruta a SQLite.

    Returns:
        Lista de dicts con cada análisis.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM analyses ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_stats(db_path: str = DEFAULT_DB_PATH) -> dict[str, int]:
    """Estadísticas agregadas.

    Returns:
        Dict con contadores por acción.
    """
    conn = _connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        by_action = dict(
            conn.execute(
                "SELECT action, COUNT(*) FROM analyses GROUP BY action"
            ).fetchall()
        )
        executed = conn.execute(
            "SELECT COUNT(*) FROM analyses WHERE executed = 1"
        ).fetchone()[0]

        return {
            "total": total,
            "compra": by_action.get("COMPRA", 0),
            "observar": by_action.get("OBSERVAR", 0),
            "evitar": by_action.get("EVITAR", 0),
            "executed": executed,
        }
    finally:
        conn.close()


def get_seen_tokens(db_path: str = DEFAULT_DB_PATH) -> set[str]:
    """Tokens ya procesados (para no reprocesarlos entre reinicios).

    Returns:
        Set de token_address vistos.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT token_address FROM seen_tokens").fetchall()
        return {row["token_address"] for row in rows}
    finally:
        conn.close()


def mark_seen(token_address: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """Registra un token como ya procesado (idempotente)."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen_tokens (token_address, seen_at) "
            "VALUES (?, ?)",
            (token_address, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def save_position(
    position: dict[str, Any],
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Registra una posición abierta (status 'open')."""
    entry = position.get("entry_price", 0.0) or 0.0
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO positions (
                opened_at, token_address, symbol, entry_price, amount_sol,
                tp_price, sl_price, trailing_active, max_price_reached, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (
                position.get("opened_at") or datetime.now(timezone.utc).isoformat(),
                position["token_address"],
                position.get("symbol", "?"),
                entry,
                position.get("amount_sol", 0.0),
                position.get("tp_price", 0.0),
                position.get("sl_price", 0.0),
                1 if position.get("trailing_active") else 0,
                position.get("max_price_reached", 0.0) or entry,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0
    finally:
        conn.close()


def get_open_positions(
    db_path: str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """Posiciones abiertas actuales."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_position_state(
    token_address: str,
    sl_price: float,
    trailing_active: bool,
    max_price_reached: float,
    db_path: str = DEFAULT_DB_PATH,
) -> bool:
    """Persiste el estado de un stop loss actualizado (trailing) en una posición abierta."""
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE positions
            SET sl_price = ?, trailing_active = ?, max_price_reached = ?
            WHERE token_address = ? AND status = 'open'
            """,
            (
                sl_price,
                1 if trailing_active else 0,
                max_price_reached,
                token_address,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def close_position(
    token_address: str,
    exit_price: float,
    pnl_sol: float,
    db_path: str = DEFAULT_DB_PATH,
) -> bool:
    """Cierra la posición abierta de un token (idempotente)."""
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE positions
            SET closed_at = ?, exit_price = ?, pnl_sol = ?, status = 'closed'
            WHERE token_address = ? AND status = 'open'
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                exit_price,
                pnl_sol,
                token_address,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_today_realized_loss(
    db_path: str = DEFAULT_DB_PATH,
) -> float:
    """Pérdidas realizadas (pnl negativo) del día en curso (SOL)."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(pnl_sol), 0.0) AS loss "
            "FROM positions "
            "WHERE status = 'closed' AND pnl_sol < 0 "
            "AND date(substr(closed_at, 1, 10)) = date('now')"
        ).fetchone()
        return float(row["loss"] or 0.0)
    finally:
        conn.close()
