"""Persistencia SQLite para análisis, detección y ciclo de ejecución."""

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

CREATE TABLE IF NOT EXISTS detected_tokens (
    token_address TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    processed_at TEXT,
    status TEXT NOT NULL DEFAULT 'DETECTED'
);
CREATE INDEX IF NOT EXISTS idx_detected_status ON detected_tokens(status);

CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    signal_id TEXT,
    token_address TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    amount_sol REAL,
    transaction_signature TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_executions_token ON executions(token_address);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);

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
    status TEXT DEFAULT 'open'
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    with _connect(db_path):
        pass
    logger.info(f"DB inicializada en {db_path}")


def register_detection(token_address: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Registra una detección y devuelve True solo si es la primera."""
    now = _utc_now()
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO detected_tokens
            (token_address, first_seen_at, last_seen_at, status)
            VALUES (?, ?, ?, 'DETECTED')
            """,
            (token_address, now, now),
        )
        if cursor.rowcount == 0:
            conn.execute(
                "UPDATE detected_tokens SET last_seen_at = ? WHERE token_address = ?",
                (now, token_address),
            )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def mark_detection_processed(
    token_address: str,
    status: str = "PROCESSED",
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            UPDATE detected_tokens
            SET processed_at = ?, status = ?, last_seen_at = ?
            WHERE token_address = ?
            """,
            (_utc_now(), status, _utc_now(), token_address),
        )
        conn.commit()
    finally:
        conn.close()


def get_detection(token_address: str, db_path: str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM detected_tokens WHERE token_address = ?",
            (token_address,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_execution(
    execution: dict[str, Any],
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Guarda/actualiza el estado de una ejecución de forma idempotente."""
    now = _utc_now()
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO executions (
                execution_id, signal_id, token_address, mode, status,
                amount_sol, transaction_signature, reason, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(execution_id) DO UPDATE SET
                status=excluded.status,
                transaction_signature=excluded.transaction_signature,
                reason=excluded.reason,
                updated_at=excluded.updated_at
            """,
            (
                execution["execution_id"],
                execution.get("signal_id"),
                execution["token_address"],
                execution["mode"],
                execution["status"],
                execution.get("amount_sol"),
                execution.get("transaction_signature"),
                execution.get("reason"),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_analysis(result: dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> int:
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
                _utc_now(),
                token.get("token_address", ""),
                token.get("symbol", "?"),
                token.get("price_usd"),
                token.get("market_cap"),
                token.get("liquidity_usd"),
                token.get("volume_5min"),
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


def get_recent_analyses(limit: int = 100, db_path: str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM analyses ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_stats(db_path: str = DEFAULT_DB_PATH) -> dict[str, int]:
    conn = _connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        by_action = dict(conn.execute(
            "SELECT action, COUNT(*) FROM analyses GROUP BY action"
        ).fetchall())
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
