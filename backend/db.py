"""SQLite persistence for AlphaForex. Plain stdlib sqlite3, no ORM. Every
table keys off `symbol` (the yfinance FX ticker, e.g. "EURUSD=X") directly —
the tracked-pairs universe is fixed and small (see pairs.py), so there's no
separate "companies" table to join through the way AlphaDesk needs for its
2,500-name NSE universe."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "alphaforex.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS thesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    thesis_text TEXT,
    risks TEXT,
    catalysts TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    period_label TEXT NOT NULL,
    est_level REAL,
    actual_level REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    currency TEXT,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL,
    description TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS daily_opens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open_rate REAL NOT NULL,
    captured_at TEXT NOT NULL,
    UNIQUE(symbol, trade_date)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


# ---- notes ----

def list_notes(symbol: str) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM notes WHERE symbol = ? ORDER BY created_at DESC", (symbol,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def add_note(symbol: str, body: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO notes (symbol, body, created_at) VALUES (?, ?, ?)",
            (symbol, body, now()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


# ---- thesis ----

def get_thesis(symbol: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM thesis WHERE symbol = ?", (symbol,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def upsert_thesis(symbol: str, thesis_text: str, risks: str, catalysts: str) -> dict:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO thesis (symbol, thesis_text, risks, catalysts, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                thesis_text = excluded.thesis_text,
                risks = excluded.risks,
                catalysts = excluded.catalysts,
                updated_at = excluded.updated_at
            """,
            (symbol, thesis_text, risks, catalysts, now()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM thesis WHERE symbol = ?", (symbol,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


# ---- forecasts (target level vs actual, analogous to estimates vs actuals) ----

def list_forecasts(symbol: str) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM forecasts WHERE symbol = ? ORDER BY period_label", (symbol,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def add_forecast(symbol: str, period_label: str, est_level) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO forecasts (symbol, period_label, est_level, updated_at) VALUES (?, ?, ?, ?)",
            (symbol, period_label, est_level, now()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM forecasts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_forecast_actual(forecast_id: int, actual_level) -> dict | None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE forecasts SET actual_level = ?, updated_at = ? WHERE id = ?",
            (actual_level, now(), forecast_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM forecasts WHERE id = ?", (forecast_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


# ---- events (personal calendar entries + the imported central-bank calendar) ----

def list_events() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM events ORDER BY event_date").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_events_for_currencies(currencies: list[str], from_date: str) -> list[dict]:
    """Calendar events tagged to any of `currencies` (a pair's base/quote),
    from `from_date` onward — used to show the relevant slice of the
    imported central-bank calendar on a pair's research page."""
    if not currencies:
        return []
    conn = get_conn()
    try:
        placeholders = ",".join("?" for _ in currencies)
        rows = conn.execute(
            f"SELECT * FROM events WHERE currency IN ({placeholders}) AND event_date >= ? ORDER BY event_date",
            (*currencies, from_date),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def add_event(symbol: str | None, currency: str | None, event_type: str, event_date: str, description: str | None, source: str | None = None) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO events (symbol, currency, event_type, event_date, description, source) VALUES (?, ?, ?, ?, ?, ?)",
            (symbol, currency, event_type, event_date, description, source),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def event_exists(currency: str, event_date: str, event_type: str) -> bool:
    """Used by the calendar bulk-import script to stay idempotent — safe to
    re-run without creating duplicate rows."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM events WHERE currency = ? AND event_date = ? AND event_type = ?",
            (currency, event_date, event_type),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ---- daily opening rates (captured once per IST trading day) ----

def get_daily_open(symbol: str, trade_date: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM daily_opens WHERE symbol = ? AND trade_date = ?", (symbol, trade_date)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_daily_opens(trade_date: str) -> dict:
    """Returns {symbol: open_rate} for every pair captured on `trade_date`."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT symbol, open_rate FROM daily_opens WHERE trade_date = ?", (trade_date,)).fetchall()
        return {r["symbol"]: r["open_rate"] for r in rows}
    finally:
        conn.close()


def upsert_daily_open(symbol: str, trade_date: str, open_rate: float) -> dict:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO daily_opens (symbol, trade_date, open_rate, captured_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date) DO UPDATE SET
                open_rate = excluded.open_rate,
                captured_at = excluded.captured_at
            """,
            (symbol, trade_date, open_rate, now()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM daily_opens WHERE symbol = ? AND trade_date = ?", (symbol, trade_date)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


# ---- full export (backup) ----

_EXPORT_TABLES = ["notes", "thesis", "forecasts", "events", "daily_opens"]


def export_all() -> dict:
    conn = get_conn()
    try:
        return {
            "exported_at": now(),
            **{table: [_row_to_dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()] for table in _EXPORT_TABLES},
        }
    finally:
        conn.close()
