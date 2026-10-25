
import pandas as pd
import streamlit as st
import yfinance as yf


# Yahoo Finance symbols for the selected Indian stocks.
YAHOO_SYMBOLS = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS",
}

# Yahoo Finance interval, requested history, and candle duration.
TIMEFRAME_SETTINGS = {
    "1m": {"interval": "1m", "period": "1d", "minutes": 1},
    "5m": {"interval": "5m", "period": "5d", "minutes": 5},
    "15m": {"interval": "15m", "period": "5d", "minutes": 15},
    "1h": {"interval": "60m", "period": "1mo", "minutes": 60},
    "1d": {"interval": "1d", "period": "1y", "minutes": None},
}


@st.cache_data(ttl=15, show_spinner=False)
def fetch_yfinance_chart(symbol, timeframe, limit=500):
    """
    Fetch real OHLCV data for an NSE-listed stock.

    Returns the same columns as MarketScope's Binance chart fetcher:
    time, open, high, low, close, volume.
    """
    if symbol not in YAHOO_SYMBOLS:
        raise ValueError(
            f"Unsupported Indian stock: {symbol}. "
            f"Supported stocks: {', '.join(YAHOO_SYMBOLS)}"
        )

    if timeframe not in TIMEFRAME_SETTINGS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    settings = TIMEFRAME_SETTINGS[timeframe]
    yahoo_symbol = YAHOO_SYMBOLS[symbol]

    try:
        df = yf.download(
            tickers=yahoo_symbol,
            period=settings["period"],
            interval=settings["interval"],
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
            timeout=15,
            multi_level_index=False,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Yahoo Finance could not fetch {symbol} data: {exc}"
        ) from exc

    if df is None or df.empty:
        raise RuntimeError(
            f"Yahoo Finance returned no data for {symbol} "
            f"at timeframe {timeframe}. The market may be closed, "
            "or the provider may temporarily be unavailable."
        )

    # Standardize column names. Some yfinance versions can return
    # MultiIndex columns even for a single ticker.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            col[0] if isinstance(col, tuple) else col
            for col in df.columns
        ]

    df.columns = [str(col).strip().lower() for col in df.columns]

    required_columns = ["open", "high", "low", "close", "volume"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise RuntimeError(
            f"Yahoo Finance response is missing columns: {missing}"
        )

    df = df[required_columns].copy()

    # Yahoo timestamps for NSE stocks are normally exchange-local.
    # Convert the index to a consistent UTC timestamp for MarketScope.
    timestamps = pd.DatetimeIndex(pd.to_datetime(df.index))

    if timestamps.tz is None:
        timestamps = timestamps.tz_localize(
            "Asia/Kolkata",
            ambiguous="NaT",
            nonexistent="NaT",
        )

    timestamps_ist = timestamps.tz_convert("Asia/Kolkata")
    now_ist = pd.Timestamp.now(tz="Asia/Kolkata")

    df["time"] = timestamps_ist
    df = df.dropna(subset=["time"])

    # Do not use an unfinished candle for indicators or alerts.
    if timeframe == "1d":
        # Yahoo's daily bars represent the NSE trading date. A bar for
        # today's date is not considered complete until the regular
        # Indian equity session has ended.
        session_end = now_ist.normalize() + pd.Timedelta(hours=15, minutes=30)

        if now_ist < session_end:
            df = df[df["time"].dt.date < now_ist.date()]
        else:
            df = df[df["time"].dt.date <= now_ist.date()]
    else:
        candle_duration = pd.Timedelta(minutes=settings["minutes"])
        df = df[
            (df["time"] + candle_duration) <= now_ist
        ]

    # Convert prices and volume to numeric and remove invalid rows.
    for col in required_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["time"] + required_columns)

    # Standardize time to UTC and remove duplicate timestamps.
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = (
        df.sort_values("time")
        .drop_duplicates(subset=["time"], keep="last")
        .tail(limit)
        .reset_index(drop=True)
    )

    if df.empty:
        raise RuntimeError(
            f"No completed {timeframe} candles are currently available "
            f"for {symbol}. Try another timeframe or check again later."
        )

    return df[["time", "open", "high", "low", "close", "volume"]]
