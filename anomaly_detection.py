import numpy as np
import pandas as pd


def detect_anomalies(df):
    """
    Detect price, volume, RSI and SMA20 anomalies.

    Returns severity, score, factors, explanations and metrics.
    Thresholds are heuristic starting points, not trading advice.
    """
    result = {
        "severity": "NORMAL",
        "score": 0,
        "factors": [],
        "explanation": [],
        "metrics": {},
    }

    if df is None or len(df) < 25:
        result["explanation"].append(
            "At least 25 candles are needed for baseline comparisons."
        )
        return result

    required = {"close", "volume"}
    if not required.issubset(df.columns):
        result["explanation"].append(
            "The data is missing required close or volume columns."
        )
        return result

    data = df.copy()
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    data["volume"] = pd.to_numeric(data["volume"], errors="coerce")
    data = data.replace([np.inf, -np.inf], np.nan)
    data = data.dropna(subset=["close", "volume"])

    if len(data) < 25:
        result["explanation"].append(
            "Not enough valid candles after cleaning the data."
        )
        return result

    close = data["close"]
    volume = data["volume"]
    latest_close = float(close.iloc[-1])
    previous_close = float(close.iloc[-2])

    if latest_close <= 0 or previous_close <= 0:
        result["explanation"].append(
            "Invalid price values prevent anomaly detection."
        )
        return result

    factors = []
    explanations = []
    score = 0
    metrics = {}

    # 1. Price movement anomaly: compare against previous 20 returns.
    returns = close.pct_change() * 100
    historical_returns = returns.iloc[-21:-1].dropna()
    latest_return = float(returns.iloc[-1])

    if len(historical_returns) >= 15:
        baseline_mean = float(historical_returns.mean())
        baseline_std = float(historical_returns.std(ddof=0))
        price_threshold = max(3 * baseline_std, 0.5)

        metrics["price_change_pct"] = round(latest_return, 3)
        metrics["normal_return_std_pct"] = round(baseline_std, 3)

        if abs(latest_return - baseline_mean) > price_threshold:
            score += 2
            factors.append("Price movement")
            explanations.append(
                f"Latest price change is {latest_return:+.2f}%, unusual "
                f"relative to recent returns (baseline mean "
                f"{baseline_mean:+.2f}%)."
            )

    # 2. Volume spike: compare against the preceding 20 candles.
    historical_volume = volume.iloc[-21:-1].dropna()
    latest_volume = float(volume.iloc[-1])

    if len(historical_volume) >= 15:
        median_volume = float(historical_volume.median())
        metrics["latest_volume"] = latest_volume
        metrics["baseline_volume_median"] = median_volume

        if median_volume > 0:
            volume_ratio = latest_volume / median_volume
            metrics["volume_multiple"] = round(volume_ratio, 2)

            if volume_ratio >= 2.0:
                score += 2
                factors.append("Volume spike")
                explanations.append(
                    f"Volume is {volume_ratio:.2f} times the median "
                    "of the preceding 20 candles."
                )

    # 3. RSI14: use existing RSI column if available, otherwise calculate.
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()
    average_loss = losses.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    relative_strength = average_gain / average_loss.replace(0, np.nan)
    calculated_rsi = 100 - (100 / (1 + relative_strength))
    calculated_rsi = calculated_rsi.mask(
        (average_loss == 0) & (average_gain > 0), 100
    )
    calculated_rsi = calculated_rsi.mask(
        (average_gain == 0) & (average_loss > 0), 0
    )
    calculated_rsi = calculated_rsi.mask(
        (average_gain == 0) & (average_loss == 0), 50
    )

    rsi_columns = [
        col for col in data.columns
        if str(col).lower() in {"rsi", "rsi14", "rsi_14"}
    ]

    if rsi_columns:
        latest_rsi = pd.to_numeric(
            data[rsi_columns[0]], errors="coerce"
        ).iloc[-1]
        if pd.isna(latest_rsi):
            latest_rsi = calculated_rsi.iloc[-1]
    else:
        latest_rsi = calculated_rsi.iloc[-1]

    if pd.notna(latest_rsi):
        latest_rsi = float(latest_rsi)
        metrics["rsi14"] = round(latest_rsi, 2)

        if latest_rsi >= 80:
            score += 1
            factors.append("High RSI")
            explanations.append(
                f"RSI is {latest_rsi:.1f}, indicating unusually strong "
                "recent upward momentum."
            )
        elif latest_rsi <= 20:
            score += 1
            factors.append("Low RSI")
            explanations.append(
                f"RSI is {latest_rsi:.1f}, indicating unusually strong "
                "recent downward momentum."
            )

    # 4. SMA20 deviation.
    if "sma20" in data.columns:
        sma20 = pd.to_numeric(data["sma20"], errors="coerce")
    else:
        sma20 = close.rolling(20).mean()

    latest_sma20 = sma20.iloc[-1]

    if pd.notna(latest_sma20) and float(latest_sma20) != 0:
        latest_sma20 = float(latest_sma20)
        deviation_pct = (
            (latest_close - latest_sma20) / latest_sma20
        ) * 100
        metrics["sma20_deviation_pct"] = round(deviation_pct, 2)

        if abs(deviation_pct) >= 3.0:
            score += 1
            factors.append("SMA20 deviation")
            explanations.append(
                f"Price is {deviation_pct:+.2f}% away from SMA20."
            )

    if score >= 4:
        severity = "HIGH"
    elif score >= 2:
        severity = "MEDIUM"
    elif score >= 1:
        severity = "LOW"
    else:
        severity = "NORMAL"

    result.update({
        "severity": severity,
        "score": score,
        "factors": factors,
        "explanation": explanations,
        "metrics": metrics,
    })

    if not explanations:
        result["explanation"].append(
            "No configured anomaly thresholds were breached by the "
            "latest completed candle."
        )

    return result
