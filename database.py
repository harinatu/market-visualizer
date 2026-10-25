import os
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# Local development: load variables from .env
load_dotenv(BASE_DIR / ".env")

# First check environment variables, then Streamlit Cloud Secrets.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    try:
        DATABASE_URL = st.secrets["DATABASE_URL"]
    except (KeyError, FileNotFoundError):
        DATABASE_URL = None

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured. "
        "Set it in your local .env file or Streamlit Cloud Secrets."
    )

# Connection pool. Connections open when first needed.
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=5,
    open=False,
    timeout=15,
)


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def initialize_database():
    """
    Execute schema.sql statements inside one transaction.
    Uses the project's schema.sql file.
    """
    schema_path = BASE_DIR / "schema.sql"

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Database schema not found: {schema_path}"
        )

    schema = schema_path.read_text(encoding="utf-8")

    # This simple split is suitable for the current schema.sql,
    # which does not contain procedural blocks or semicolons in strings.
    statements = [
        statement.strip()
        for statement in schema.split(";")
        if statement.strip()
    ]

    with pool.connection() as conn:
        with conn.transaction():
            for statement in statements:
                conn.execute(statement)


# --------------------------------------------------
# INSTRUMENTS
# --------------------------------------------------

def get_instruments():
    """Return all configured market instruments."""
    with pool.connection() as conn:
        return conn.execute("""
            SELECT id, symbol, name, asset_type, exchange
            FROM instruments
            ORDER BY
                CASE asset_type
                    WHEN 'crypto' THEN 1
                    ELSE 2
                END,
                symbol
        """).fetchall()


# --------------------------------------------------
# CANDLES
# --------------------------------------------------

def save_candle(
    instrument_id,
    candle_time,
    open_price,
    high,
    low,
    close,
    volume,
    is_closed=True,
    timeframe="1m",
):
    """Insert a candle or update its existing values."""
    with pool.connection() as conn:
        conn.execute("""
            INSERT INTO candles (
                instrument_id,
                timeframe,
                candle_time,
                open,
                high,
                low,
                close,
                volume,
                is_closed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (
                instrument_id,
                timeframe,
                candle_time
            )
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                is_closed = EXCLUDED.is_closed
        """, (
            instrument_id,
            timeframe,
            candle_time,
            open_price,
            high,
            low,
            close,
            volume,
            is_closed,
        ))


def get_candles(instrument_id, limit=300):
    """Return recent stored 1-minute candles chronologically."""
    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT
                candle_time,
                open,
                high,
                low,
                close,
                volume,
                is_closed
            FROM (
                SELECT
                    candle_time,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    is_closed
                FROM candles
                WHERE instrument_id = %s
                  AND timeframe = '1m'
                ORDER BY candle_time DESC
                LIMIT %s
            ) AS recent
            ORDER BY candle_time ASC
        """, (instrument_id, limit)).fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "is_closed",
        ],
    )


# --------------------------------------------------
# MARKET ALERTS
# --------------------------------------------------

def save_alert(
    instrument_id,
    signal,
    evidence_strength,
    risk_level,
    price,
    explanation,
    invalidation,
    fingerprint,
    timeframe="15m",
):
    """
    Insert an alert once per instrument and fingerprint.
    Returns True if inserted, False if already present.
    """
    with pool.connection() as conn:
        result = conn.execute("""
            INSERT INTO alerts (
                instrument_id,
                signal,
                evidence_strength,
                risk_level,
                timeframe,
                price,
                explanation,
                invalidation,
                fingerprint
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument_id, fingerprint)
            DO NOTHING
            RETURNING id
        """, (
            instrument_id,
            signal,
            evidence_strength,
            risk_level,
            timeframe,
            price,
            explanation,
            invalidation,
            fingerprint,
        ))

        return result.fetchone() is not None


def get_alerts(instrument_id=None, limit=50):
    """Return the newest market alerts."""
    with pool.connection() as conn:
        if instrument_id is None:
            rows = conn.execute("""
                SELECT
                    a.created_at,
                    i.symbol,
                    a.timeframe,
                    a.signal,
                    a.evidence_strength,
                    a.risk_level,
                    a.price,
                    a.explanation,
                    a.invalidation
                FROM alerts AS a
                JOIN instruments AS i
                  ON i.id = a.instrument_id
                ORDER BY a.created_at DESC
                LIMIT %s
            """, (limit,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT
                    a.created_at,
                    i.symbol,
                    a.timeframe,
                    a.signal,
                    a.evidence_strength,
                    a.risk_level,
                    a.price,
                    a.explanation,
                    a.invalidation
                FROM alerts AS a
                JOIN instruments AS i
                  ON i.id = a.instrument_id
                WHERE a.instrument_id = %s
                ORDER BY a.created_at DESC
                LIMIT %s
            """, (instrument_id, limit)).fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "time",
            "symbol",
            "timeframe",
            "signal",
            "evidence",
            "risk",
            "price",
            "explanation",
            "invalidation",
        ],
    )


# --------------------------------------------------
# ANOMALY EVENTS
# --------------------------------------------------

def save_anomaly_event(
    instrument_id,
    symbol,
    timeframe,
    candle_time,
    price,
    severity,
    score,
    factors,
    explanation,
    metrics,
):
    """
    Save an anomaly once per instrument, timeframe and candle.
    Returns True if inserted, False if the event already exists.
    """
    factors_text = ", ".join(factors) if factors else "None"
    explanation_text = (
        "\n".join(explanation)
        if explanation
        else "No explanation available."
    )

    with pool.connection() as conn:
        result = conn.execute("""
            INSERT INTO anomaly_events (
                instrument_id,
                symbol,
                timeframe,
                candle_time,
                price,
                severity,
                score,
                factors,
                explanation,
                metrics
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (
                instrument_id,
                timeframe,
                candle_time
            )
            DO NOTHING
            RETURNING id
        """, (
            instrument_id,
            symbol,
            timeframe,
            candle_time,
            price,
            severity,
            score,
            factors_text,
            explanation_text,
            json.dumps(metrics or {}),
        ))

        return result.fetchone() is not None


def get_anomaly_events(
    symbol=None,
    severity=None,
    limit=100,
):
    """Return recent anomaly events with optional filters."""
    clauses = []
    params = []

    if symbol and symbol != "All":
        clauses.append("symbol = %s")
        params.append(symbol)

    if severity and severity != "All":
        clauses.append("severity = %s")
        params.append(severity)

    where_sql = (
        "WHERE " + " AND ".join(clauses)
        if clauses
        else ""
    )

    params.append(limit)

    with pool.connection() as conn:
        rows = conn.execute(
            f"""
                SELECT
                    created_at,
                    symbol,
                    timeframe,
                    candle_time,
                    price,
                    severity,
                    score,
                    factors,
                    explanation
                FROM anomaly_events
                {where_sql}
                ORDER BY candle_time DESC
                LIMIT %s
            """,
            params,
        ).fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "saved_at",
            "symbol",
            "timeframe",
            "candle_time",
            "price",
            "severity",
            "score",
            "factors",
            "explanation",
        ],
    )


# --------------------------------------------------
# LOCAL DATABASE TEST
# --------------------------------------------------

if __name__ == "__main__":
    try:
        pool.open(wait=True)
        initialize_database()

        with pool.connection() as conn:
            name = conn.execute(
                "SELECT current_database()"
            ).fetchone()[0]

        print(f"Connected to PostgreSQL database: {name}")
        print("Database schema and instruments initialized.")

    except Exception as exc:
        print(f"Database setup failed: {exc}")
        raise

    finally:
        pool.close()