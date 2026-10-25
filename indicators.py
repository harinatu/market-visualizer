
import hashlib

import numpy as np
import pandas as pd


TIMEFRAME_FLOORS = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "1d": "1D",
}


def calculate_indicators(df):
    """Calculate SMA20, SMA50, price change, and volume spikes."""
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    result = df.copy()

    required = [
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    missing = [
        column for column in required
        if column not in result.columns
    ]

    if missing:
        raise ValueError(
            "Missing columns needed for indicators: "
            + ", ".join(missing)
        )

    result["time"] = pd.to_datetime(
        result["time"],
        utc=True,
        errors="coerce",
    )

    for column in ["open", "high", "low", "close", "volume"]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result = (
        result.dropna(
            subset=["time", "open", "high", "low", "close", "volume"]
        )
        .sort_values("time")
        .drop_duplicates(subset=["time"], keep="last")
        .reset_index(drop=True)
    )

    if result.empty:
        return result

    # Moving averages
    result["sma20"] = (
        result["close"]
        .rolling(window=20, min_periods=20)
        .mean()
    )

    result["sma50"] = (
        result["close"]
        .rolling(window=50, min_periods=50)
        .mean()
    )

    # Percentage change from the previous candle
    result["price_change_pct"] = (
        result["close"].pct_change() * 100
    )

    # Compare volume with the previous 20 candles
    previous_volume = (
        result["volume"]
        .shift(1)
        .rolling(window=20, min_periods=10)
        .mean()
    )

    result["volume_ratio"] = (
        result["volume"]
        / previous_volume.replace(0, np.nan)
    )

    result["volume_spike"] = result["volume_ratio"] >= 2.0

    return result


def classify_signal(df, timeframe="15m"):
    """
    Classify the latest completed candle.

    Signals are rule-based observations, not guaranteed predictions.
    Fingerprints include timeframe and candle window for deduplication.
    """
    if df is None or df.empty:
        return None

    required_columns = [
        "time",
        "open",
        "close",
        "sma20",
        "sma50",
        "volume_spike",
    ]

    missing = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing required columns. Run calculate_indicators(df) first. "
            "Missing: " + ", ".join(missing)
        )

    row = df.iloc[-1]

    # Insufficient data for moving averages
    if (
        pd.isna(row["time"])
        or pd.isna(row["sma20"])
        or pd.isna(row["sma50"])
        or pd.isna(row["close"])
        or pd.isna(row["open"])
    ):
        return {
            "signal": "NEUTRAL",
            "evidence": "Low",
            "risk": "High",
            "explanation": (
                "Insufficient valid candle history to calculate moving "
                "averages. At least 50 valid candles are needed."
            ),
            "invalidation": (
                "Wait for at least 50 valid completed candles and recalculate."
            ),
            "fingerprint": None,
        }

    bullish = []
    bearish = []

    # Factor 1: Price relative to SMA20
    if row["close"] > row["sma20"]:
        bullish.append("Price is above SMA20.")
    elif row["close"] < row["sma20"]:
        bearish.append("Price is below SMA20.")

    # Factor 2: SMA20 relative to SMA50
    if row["sma20"] > row["sma50"]:
        bullish.append("SMA20 is above SMA50.")
    elif row["sma20"] < row["sma50"]:
        bearish.append("SMA20 is below SMA50.")

    # Factor 3: Volume spike and candle direction
    volume_spike = (
        pd.notna(row["volume_spike"])
        and bool(row["volume_spike"])
    )

    if volume_spike:
        if row["close"] > row["open"]:
            bullish.append(
                "Volume is at least twice its recent average "
                "on an upward candle."
            )
        elif row["close"] < row["open"]:
            bearish.append(
                "Volume is at least twice its recent average "
                "on a downward candle."
            )

    # Determine the signal
    if len(bullish) > len(bearish):
        signal = "BULLISH"
        reasons = bullish
        opposite = bearish

    elif len(bearish) > len(bullish):
        signal = "BEARISH"
        reasons = bearish
        opposite = bullish

    else:
        signal = "NEUTRAL"
        reasons = bullish + bearish
        opposite = []

    evidence_count = len(reasons)

    if evidence_count >= 3:
        evidence = "High"
    elif evidence_count == 2:
        evidence = "Medium"
    else:
        evidence = "Low"

    # Heuristic risk label, not a probability
    if signal == "NEUTRAL" or evidence_count <= 1:
        risk = "High"
    else:
        risk = "Moderate"

    if signal == "NEUTRAL":
        explanation = (
            "The selected factors do not show a clear directional agreement."
        )
    else:
        explanation = " ".join(reasons)

    if opposite:
        explanation += (
            " Conflicting evidence: " + " ".join(opposite)
        )

    invalidation = (
        "Reassess the signal if price crosses the moving averages in the "
        "opposite direction, volume conditions change, or a subsequent "
        "candle contradicts the current trend."
    )

    # Create a stable fingerprint for the selected timeframe and candle window
    floor_rule = TIMEFRAME_FLOORS.get(timeframe, "15min")

    candle_time = pd.Timestamp(row["time"])

    if candle_time.tzinfo is None:
        candle_time = candle_time.tz_localize("UTC")
    else:
        candle_time = candle_time.tz_convert("UTC")

    window = candle_time.floor(floor_rule).isoformat()

    fingerprint_text = f"{timeframe}:{signal}:{window}"

    fingerprint = hashlib.sha256(
        fingerprint_text.encode("utf-8")
    ).hexdigest()[:40]

    return {
        "signal": signal,
        "evidence": evidence,
        "risk": risk,
        "explanation": explanation,
        "invalidation": invalidation,
        "fingerprint": fingerprint,
    }
