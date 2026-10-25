import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env")

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=5,
    open=False,
)


def initialize_database():
    """Execute schema statements inside one transaction."""
    schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    statements = [statement.strip() for statement in schema.split(";") if statement.strip()]

    with pool.connection() as conn:
        with conn.transaction():
            for statement in statements:
                conn.execute(statement)


def get_instruments():
    with pool.connection() as conn:
        return conn.execute("""
            SELECT id, symbol, name, asset_type, exchange
            FROM instruments
            ORDER BY
                CASE asset_type WHEN 'crypto' THEN 1 ELSE 2 END,
                symbol
        """).fetchall()


def save_candle(
    instrument_id, candle_time, open_price, high, low,
    close, volume, is_closed=True, timeframe="1m"
):
    """Insert or update a candle identified by instrument, timeframe and open time."""
    with pool.connection() as conn:
        conn.execute("""
            INSERT INTO candles (
                instrument_id, timeframe, candle_time,
                open, high, low, close, volume, is_closed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument_id, timeframe, candle_time)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                is_closed = EXCLUDED.is_closed
        """, (
            instrument_id, timeframe, candle_time,
            open_price, high, low, close, volume, is_closed
        ))


def get_candles(instrument_id, limit=300):
    """Return the latest stored 1-minute candles in chronological order."""
    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT candle_time, open, high, low, close, volume, is_closed
            FROM (
                SELECT candle_time, open, high, low, close, volume, is_closed
                FROM candles
                WHERE instrument_id = %s AND timeframe = '1m'
                ORDER BY candle_time DESC
                LIMIT %s
            ) recent
            ORDER BY candle_time ASC
        """, (instrument_id, limit)).fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "time", "open", "high", "low", "close", "volume", "is_closed"
        ],
    )


def save_alert(
    instrument_id, signal, evidence_strength, risk_level,
    price, explanation, invalidation, fingerprint, timeframe="15m"
):
    """
    Insert an alert once per (instrument_id, fingerprint).
    Returns True if inserted and False if a duplicate fingerprint was skipped.
    """
    with pool.connection() as conn:
        result = conn.execute("""
            INSERT INTO alerts (
                instrument_id, signal, evidence_strength, risk_level,
                timeframe, price, explanation, invalidation, fingerprint
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument_id, fingerprint) DO NOTHING
            RETURNING id
        """, (
            instrument_id, signal, evidence_strength, risk_level,
            timeframe, price, explanation, invalidation, fingerprint
        ))
        return result.fetchone() is not None


def get_alerts(instrument_id=None, limit=50):
    """Return newest alerts, including the timeframe that generated each alert."""
    with pool.connection() as conn:
        if instrument_id is None:
            rows = conn.execute("""
                SELECT a.created_at, i.symbol, a.timeframe, a.signal,
                       a.evidence_strength, a.risk_level,
                       a.price, a.explanation, a.invalidation
                FROM alerts a
                JOIN instruments i ON i.id = a.instrument_id
                ORDER BY a.created_at DESC
                LIMIT %s
            """, (limit,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT a.created_at, i.symbol, a.timeframe, a.signal,
                       a.evidence_strength, a.risk_level,
                       a.price, a.explanation, a.invalidation
                FROM alerts a
                JOIN instruments i ON i.id = a.instrument_id
                WHERE a.instrument_id = %s
                ORDER BY a.created_at DESC
                LIMIT %s
            """, (instrument_id, limit)).fetchall()

    return pd.DataFrame(rows, columns=[
        "time", "symbol", "timeframe", "signal", "evidence",
        "risk", "price", "explanation", "invalidation"
    ])


if __name__ == "__main__":
    try:
        pool.open(wait=True)
        initialize_database()
        with pool.connection() as conn:
            name = conn.execute("SELECT current_database()").fetchone()[0]
        print(f"Connected to PostgreSQL database: {name}")
        print("Database schema and instruments initialized.")
    except Exception as exc:
        print(f"Database setup failed: {exc}")
        raise
    finally:
        pool.close()


def save_anomaly_event(
    instrument_id, symbol, timeframe, candle_time, price, severity, score,
    factors, explanation, metrics
):
    """Save an anomaly once per instrument/timeframe/candle. Returns True if new."""
    import json

    factors_text = ", ".join(factors) if factors else "None"
    explanation_text = "\n".join(explanation) if explanation else "No explanation available."
    with pool.connection() as conn:
        result = conn.execute(
            """
            INSERT INTO anomaly_events (
                instrument_id, symbol, timeframe, candle_time, price, severity,
                score, factors, explanation, metrics
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (instrument_id, timeframe, candle_time) DO NOTHING
            RETURNING id
            """,
            (instrument_id, symbol, timeframe, candle_time, price, severity,
             score, factors_text, explanation_text, json.dumps(metrics or {})),
        )
        return result.fetchone() is not None


def get_anomaly_events(symbol=None, severity=None, limit=100):
    """Fetch newest stored anomaly events, with optional symbol/severity filters."""
    clauses = []
    params = []
    if symbol and symbol != "All":
        clauses.append("symbol = %s")
        params.append(symbol)
    if severity and severity != "All":
        clauses.append("severity = %s")
        params.append(severity)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with pool.connection() as conn:
        rows = conn.execute(
            f"""SELECT created_at, symbol, timeframe, candle_time, price,
                       severity, score, factors, explanation
                FROM anomaly_events {where_sql}
                ORDER BY candle_time DESC LIMIT %s""",
            params,
        ).fetchall()
    return pd.DataFrame(rows, columns=[
        "saved_at", "symbol", "timeframe", "candle_time", "price",
        "severity", "score", "factors", "explanation"
    ])
