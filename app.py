import pandas as pd
import requests
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from database import (
    pool,
    initialize_database,
    get_instruments,
    get_alerts,
    save_alert,
    save_anomaly_event,
    get_anomaly_events,
)
from indicators import calculate_indicators, classify_signal
from stock_data import fetch_yfinance_chart
from anomaly_detection import detect_anomalies

# ----------------------------- CONFIG -----------------------------
USD_TO_INR = 92.30
BG = "#050505"
PANEL = "#10141D"
BORDER = "#2B3445"
MUTED = "#9AA7BA"
BLUE = "#60A5FA"
GREEN = "#22C55E"
RED = "#EF4444"
AMBER = "#F59E0B"
PURPLE = "#B4A1FF"

st.set_page_config(
    page_title="MarketScope | Market Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    f"""
    <style>
      :root {{
        --ms-bg: #05070B;
        --ms-panel: #10141D;
        --ms-panel-raised: #151B27;
        --ms-border: #2B3445;
        --ms-text: #F3F6FC;
        --ms-muted: #9AA7BA;
        --ms-blue: #60A5FA;
      }}
      .stApp {{
        background:
          radial-gradient(ellipse at 12% 0%, rgba(37, 99, 235, .10), transparent 32%),
          radial-gradient(ellipse at 92% 12%, rgba(124, 58, 237, .07), transparent 28%),
          var(--ms-bg);
        color: var(--ms-text);
      }}
      [data-testid="stHeader"] {{ background: rgba(5,7,11,.92); }}
      [data-testid="stToolbar"] {{ right: 1rem; }}
      [data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display:none !important; }}
      .block-container {{ max-width: 1660px; padding-top: 1.4rem; padding-bottom: 2.4rem; }}
      h1,h2,h3,h4,p,span,label {{ color: var(--ms-text); }}
      h1 {{ letter-spacing: -.045em; }}
      h2,h3 {{ letter-spacing: -.025em; }}
      div[data-testid="stMetric"] {{
        background: linear-gradient(145deg, #171E2B 0%, #10141D 72%);
        border: 1px solid #303B50;
        padding: 15px 17px;
        border-radius: 14px;
        min-height: 102px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,.025), 0 8px 22px rgba(0,0,0,.12);
      }}
      div[data-testid="stMetricLabel"] p {{ color: #A8B4C7 !important; font-size: .78rem; }}
      div[data-testid="stMetricValue"] {{ color: #F8FAFC !important; font-weight: 750; letter-spacing: -.03em; }}
      div[data-testid="stVerticalBlockBorderWrapper"] > div {{
        border: 1px solid var(--ms-border);
        border-radius: 15px;
        background: linear-gradient(150deg, rgba(20,27,40,.97), rgba(11,15,23,.98));
        box-shadow: 0 10px 30px rgba(0,0,0,.16), inset 0 1px 0 rgba(255,255,255,.025);
      }}
      div[data-testid="stAlert"] {{
        border-radius: 11px;
        border: 1px solid #344155;
        background: #141B28;
      }}
      div[data-testid="stDataFrame"] {{
        border: 1px solid #303B50;
        border-radius: 11px;
        overflow: hidden;
      }}
      [data-baseweb="select"] > div, [data-baseweb="input"] > div {{
        background: #141B28;
        border-color: #354156;
        border-radius: 10px;
      }}
      button[kind="secondary"] {{
        background: #151D2B;
        border: 1px solid #354156;
        border-radius: 10px;
      }}
      button[kind="secondary"]:hover {{
        border-color: #60A5FA;
        color: #BFDBFE;
      }}
      .ms-brand {{
        font-size: 2rem;
        font-weight: 850;
        letter-spacing: -.055em;
        color: #FFFFFF;
        line-height: 1.15;
      }}
      .ms-brand-mark {{
        display:inline-flex; align-items:center; justify-content:center;
        width:35px; height:35px; margin-right:8px; border-radius:11px;
        color:#DCEBFF; background:linear-gradient(135deg,#2563EB,#7C3AED);
        box-shadow:0 5px 20px rgba(59,130,246,.24);
      }}
      .ms-subtitle {{ color:#A4B0C3; font-size:.88rem; margin-top:5px; }}
      .ms-muted {{ color:var(--ms-muted); font-size:.77rem; letter-spacing:.035em; }}
      .ms-section {{
        padding: 10px 13px;
        border-radius: 10px;
        background: linear-gradient(90deg, rgba(59,130,246,.16), rgba(124,58,237,.07), rgba(16,20,29,0));
        border-left: 3px solid #60A5FA;
        font-size: 1.04rem;
        font-weight: 750;
        color: #F8FAFC;
      }}
      .ms-chip {{ display:inline-block; padding:4px 9px; border:1px solid #354156; border-radius:999px; color:#D4DEED; background:#151D2B; font-size:.72rem; }}
      .ms-factor {{
        background: linear-gradient(145deg, #171D29, #0E121A);
        border: 1px solid #303B50;
        border-radius: 13px;
        padding: 15px;
        min-height: 158px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,.025);
      }}
      .ms-factor-title {{ font-size:.86rem; font-weight:700; color:#F4F7FB; }}
      .ms-factor-value {{ font-size:1.65rem; font-weight:800; margin-top:10px; color:#FFFFFF; letter-spacing:-.035em; }}
      .ms-factor-note {{ font-size:.75rem; color:#A8B4C7; margin-top:8px; line-height:1.55; }}
      .ms-rule {{ border-left:3px solid {RED}; padding:13px 15px; background:linear-gradient(90deg,rgba(239,68,68,.12),rgba(21,27,39,.65)); border-radius:0 10px 10px 0; }}
      .ms-footer {{ color:#7D8BA1; font-size:.73rem; padding-top:18px; text-align:center; }}
      [data-testid="stCaptionContainer"] p {{ color:#9AA7BA; }}
      hr {{ border-color:#293449; }}
      @media (max-width: 900px) {{
        .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
        .ms-brand {{ font-size:1.65rem; }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------- DATABASE -----------------------------
@st.cache_resource
def setup_database():
    if pool.closed:
        pool.open(wait=True)
    initialize_database()
    return True

try:
    setup_database()
except Exception as exc:
    st.error("Cannot connect to PostgreSQL. Check PostgreSQL and your .env file.")
    st.code(str(exc))
    st.stop()


# ----------------------------- DATA FETCH -----------------------------
@st.cache_data(ttl=5, show_spinner=False)
def fetch_binance_chart(symbol, timeframe, limit=500):
    url = "https://data-api.binance.vision/api/v3/klines"
    response = requests.get(
        url,
        params={"symbol": symbol, "interval": timeframe, "limit": limit},
        timeout=10,
    )
    response.raise_for_status()
    rows = response.json()
    columns = [
        "time_ms", "open", "high", "low", "close", "volume",
        "close_time_ms", "quote_volume", "trade_count", "taker_buy_volume",
        "taker_buy_quote_volume", "ignore",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time_ms"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    now_ms = pd.Timestamp.now(tz="UTC").timestamp() * 1000
    df = df[pd.to_numeric(df["close_time_ms"], errors="coerce") < now_ms]
    df = df.dropna(subset=["time", "open", "high", "low", "close", "volume"])
    return df[["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def configure_currency(symbol, asset_type):
    asset_type = str(asset_type).lower()
    symbol_upper = str(symbol).upper()
    if asset_type in {"stock", "equity"}:
        return {"currency": "INR", "symbol": "₹", "rate": 1.0, "converted": False}
    if asset_type == "crypto" and symbol_upper.endswith(("USDT", "USDC", "USD")):
        return {"currency": "INR", "symbol": "₹", "rate": USD_TO_INR, "converted": True}
    return {"currency": "Original quote currency", "symbol": "", "rate": 1.0, "converted": False}


def convert_prices_to_inr(df, currency_info):
    df = df.copy()
    rate = currency_info["rate"]
    if rate != 1.0:
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = df[col] * rate
    return df


def money(value, currency_symbol):
    if pd.isna(value):
        return "—"
    return f"{currency_symbol}{float(value):,.2f}"


def style_figure(fig, height=330):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        margin=dict(l=8, r=8, t=16, b=8),
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(family="Inter, Arial, sans-serif", color="#A3A3A3", size=10),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=9)),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=BORDER, rangeslider_visible=False)
    fig.update_yaxes(gridcolor="#1D1D1D", zeroline=False, linecolor=BORDER)
    return fig


def make_line_figure(df, currency_symbol, timeframe):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time"], y=df["close"], mode="lines", name="Price",
        line=dict(color="#3B82F6", width=2),
        fill="tozeroy", fillcolor="rgba(59,130,246,.08)",
        hovertemplate=f"%{{x}}<br>Price: {currency_symbol}%{{y:,.2f}}<extra></extra>",
    ))
    if "sma20" in df:
        fig.add_trace(go.Scatter(x=df["time"], y=df["sma20"], name=f"SMA20 · {timeframe}", line=dict(color=AMBER, width=1.2)))
    if "sma50" in df:
        fig.add_trace(go.Scatter(x=df["time"], y=df["sma50"], name=f"SMA50 · {timeframe}", line=dict(color=PURPLE, width=1.2)))
    fig.update_layout(yaxis_tickprefix=currency_symbol)
    return style_figure(fig)


def make_candle_figure(df, currency_symbol, timeframe):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.035, row_heights=[.78, .22])
    fig.add_trace(go.Candlestick(
        x=df["time"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="OHLC", increasing_line_color=GREEN, decreasing_line_color=RED,
        increasing_fillcolor=GREEN, decreasing_fillcolor=RED,
        hovertemplate="%{x}<br>O: %{open:,.2f}<br>H: %{high:,.2f}<br>L: %{low:,.2f}<br>C: %{close:,.2f}<extra></extra>",
    ), row=1, col=1)
    for col, color, name in [("sma20", AMBER, "SMA20"), ("sma50", PURPLE, "SMA50")]:
        if col in df:
            fig.add_trace(go.Scatter(x=df["time"], y=df[col], name=f"{name} · {timeframe}", line=dict(color=color, width=1.2)), row=1, col=1)
    colors = [GREEN if c >= o else RED for o, c in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(x=df["time"], y=df["volume"], marker_color=colors, name="Volume", hovertemplate="Volume: %{y:,.2f}<extra></extra>"), row=2, col=1)
    fig.update_layout(yaxis_tickprefix=currency_symbol, showlegend=True)
    fig.update_xaxes(rangeslider_visible=False)
    return style_figure(fig, height=330)


# ----------------------------- LOAD INSTRUMENTS -----------------------------
st.markdown('<div class="ms-brand"><span class="ms-brand-mark">◈</span>MarketScope</div>', unsafe_allow_html=True)
st.markdown('<div class="ms-subtitle">Real-time market intelligence · Technical signals · Explainable anomaly detection</div>', unsafe_allow_html=True)
st.write("")
try:
    instruments = get_instruments()
except Exception as exc:
    st.error(f"Could not load instruments from PostgreSQL: {exc}")
    st.stop()
if not instruments:
    st.warning("No instruments found in PostgreSQL. Add instruments to the instruments table first.")
    st.stop()

instrument_map = {
    f"{row[1]} — {row[2]}": {"id": row[0], "symbol": row[1], "name": row[2], "type": row[3], "exchange": row[4]}
    for row in instruments
}
labels = list(instrument_map.keys())

# Main top controls, not hidden away in a sidebar.
control1, control2, control3, control4 = st.columns([2.2, 1.0, 1.0, 1.2])
with control1:
    selected_label = st.selectbox("ASSET", labels, key="main_asset")
selected = instrument_map[selected_label]
with control2:
    timeframe = st.selectbox("TIMEFRAME", ["1m", "5m", "15m", "1h", "4h", "1d"], index=1, key="main_timeframe")
with control3:
    st.selectbox("MARKET", ["Auto detect"], disabled=True, key="market_mode")
with control4:
    st.markdown(f'<div style="padding-top:27px;text-align:right;color:#9CA3AF;font-size:.8rem">● Selected: <b style="color:#E5E7EB">{selected["exchange"]}</b></div>', unsafe_allow_html=True)


# ----------------------------- MAIN DASHBOARD -----------------------------
@st.fragment(run_every=5)
def render_dashboard():
    instrument = instrument_map[st.session_state["main_asset"]]
    symbol = instrument["symbol"]
    asset_type = str(instrument["type"]).lower()
    current_tf = st.session_state["main_timeframe"]

    try:
        if asset_type == "crypto":
            raw_df = fetch_binance_chart(symbol, current_tf, limit=500)
            data_source = "Binance"
        elif asset_type in {"stock", "equity"}:
            raw_df = fetch_yfinance_chart(symbol, current_tf, limit=500)
            data_source = "Yahoo Finance"
        else:
            st.error(f"Unsupported asset type '{asset_type}' for {symbol}.")
            return
    except Exception as exc:
        st.error(f"Could not fetch market data for {symbol}: {exc}")
        return

    if raw_df is None or raw_df.empty:
        st.warning(f"No completed candles available for {symbol} at {current_tf}. Try another timeframe or asset.")
        return

    currency_info = configure_currency(symbol, asset_type)
    df = convert_prices_to_inr(raw_df, currency_info)
    df = calculate_indicators(df)
    if df is None or df.empty:
        st.warning("Waiting for valid market data and indicators.")
        return

    currency_symbol = currency_info["symbol"]
    latest = df.iloc[-1]
    previous = float(df["close"].iloc[-2]) if len(df) > 1 else float(latest["open"])
    latest_close = float(latest["close"])
    change_pct = ((latest_close - previous) / previous * 100) if previous else 0.0
    anomaly = detect_anomalies(df)
    signal = classify_signal(df, timeframe=current_tf)
    latest_time = df["time"].iloc[-1]

    # Persist only non-normal anomalies; unique DB key prevents duplicate candle records.
    anomaly_saved = False
    if anomaly["severity"] != "NORMAL":
        try:
            anomaly_saved = save_anomaly_event(
                instrument["id"], symbol, current_tf, latest_time, latest_close,
                anomaly["severity"], anomaly["score"], anomaly["factors"],
                anomaly["explanation"], anomaly["metrics"],
            )
        except Exception as exc:
            st.warning(f"Anomaly detected, but PostgreSQL save failed: {exc}")

    # Header price strip.
    status_col, price_col, change_col, candles_col = st.columns([1.7, 1.3, 1.0, 1.2])
    with status_col:
        st.markdown(f"<div class='ms-muted'>LIVE DATA SOURCE</div><div style='font-size:1rem;font-weight:650;margin-top:5px'>● {data_source} <span style='color:#737373;font-weight:400'>· {current_tf}</span></div>", unsafe_allow_html=True)
    with price_col:
        st.markdown(f"<div class='ms-muted'>LATEST PRICE · {currency_info['currency']}</div><div style='font-size:1.35rem;font-weight:750;margin-top:3px'>{money(latest_close, currency_symbol)}</div>", unsafe_allow_html=True)
    with change_col:
        change_color = GREEN if change_pct >= 0 else RED
        st.markdown(f"<div class='ms-muted'>LAST CANDLE CHANGE</div><div style='font-size:1.2rem;font-weight:750;color:{change_color};margin-top:5px'>{change_pct:+.2f}%</div>", unsafe_allow_html=True)
    with candles_col:
        st.markdown(f"<div class='ms-muted'>COMPLETED CANDLES</div><div style='font-size:1.2rem;font-weight:750;margin-top:5px'>{len(df):,}</div>", unsafe_allow_html=True)

    # Side-by-side charts, both visible at once.
    line_col, candle_col = st.columns(2, gap="medium")
    with line_col:
        with st.container(border=True):
            st.markdown(f"**Line chart** <span style='color:#737373;font-size:.75rem;float:right'>{symbol} · {currency_info['currency']}</span>", unsafe_allow_html=True)
            st.caption(f"Price movement with SMA20 and SMA50 · {current_tf}")
            st.plotly_chart(make_line_figure(df, currency_symbol, current_tf), width="stretch", key=f"line_{symbol}_{current_tf}")
    with candle_col:
        with st.container(border=True):
            st.markdown(f"**Candlestick chart** <span style='color:#737373;font-size:.75rem;float:right'>{symbol} · {currency_info['currency']}</span>", unsafe_allow_html=True)
            st.caption(f"OHLC candles and volume · {current_tf}")
            st.plotly_chart(make_candle_figure(df, currency_symbol, current_tf), width="stretch", key=f"candle_{symbol}_{current_tf}")

    # Market signal explanation section.
    st.write("")
    with st.container(border=True):
        st.markdown("<div class=\"ms-section\">Market signal explanation</div>", unsafe_allow_html=True)
        if signal:
            sig = str(signal.get("signal", "NEUTRAL")).upper()
            sig_color = GREEN if sig == "BULLISH" else RED if sig == "BEARISH" else "#A3A3A3"
            st.markdown(f"<span style='color:{sig_color};font-weight:750'>● {sig}</span> <span style='color:#737373;font-size:.8rem'> · {signal.get('evidence', 0)} supporting conditions</span>", unsafe_allow_html=True)
            sma20_value = latest.get("sma20", float("nan"))
            sma50_value = latest.get("sma50", float("nan"))
            rsi_value = latest.get("rsi14", latest.get("rsi", float("nan")))
            deviation = ((latest_close - float(sma20_value)) / float(sma20_value) * 100) if pd.notna(sma20_value) and float(sma20_value) else float("nan")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric(f"SMA20 · {current_tf}", money(sma20_value, currency_symbol))
            s2.metric(f"SMA50 · {current_tf}", money(sma50_value, currency_symbol))
            s3.metric("RSI14", f"{float(rsi_value):.1f}" if pd.notna(rsi_value) else "Calculating")
            s4.metric("Price vs SMA20", f"{deviation:+.2f}%" if pd.notna(deviation) else "Calculating")
            why_col, risk_col = st.columns([2, 1])
            with why_col:
                st.markdown("**What the indicators say**")
                st.write(signal.get("explanation", "Signal explanation unavailable."))
            with risk_col:
                st.markdown("**Risk context**")
                st.write(f"**Risk:** {signal.get('risk', 'Not available')}")
                st.write(signal.get("invalidation", "No invalidation condition available."))
            if signal.get("fingerprint") and sig != "NEUTRAL":
                try:
                    save_alert(instrument["id"], sig, signal.get("evidence", 0), signal.get("risk", "Unknown"), latest_close, signal.get("explanation", ""), signal.get("invalidation", ""), signal["fingerprint"], timeframe=current_tf)
                except Exception as exc:
                    st.warning(f"Could not save signal alert: {exc}")
        else:
            st.info("Signal unavailable: there may not be enough valid indicator data yet.")
        st.caption("Signals summarize rule-based indicator conditions; they do not predict prices or guarantee outcomes.")

    # Anomaly section — visually prominent and wide.
    st.write("")
    with st.container(border=True):
        st.markdown("<div class=\"ms-section\">◉ &nbsp; Anomaly detection</div>", unsafe_allow_html=True)
        st.caption("Unusual activity, made understandable. Four independent rules are evaluated on the selected asset's own candle history.")
        sev = anomaly["severity"]
        sev_color = RED if sev == "HIGH" else AMBER if sev == "MEDIUM" else BLUE if sev == "LOW" else "#A3A3A3"
        recent_count = 0
        try:
            recent_df = get_anomaly_events(symbol=symbol, severity="All", limit=100)
            recent_count = len(recent_df)
        except Exception:
            recent_df = pd.DataFrame()
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            st.metric("Latest severity", sev)
        with a2:
            st.metric("Anomaly score", f"{anomaly['score']} / 6")
        with a3:
            st.metric("Triggered factors", f"{len(anomaly['factors'])} / 4")
        with a4:
            st.metric("Saved events", recent_count)
        st.markdown(f"<div style='height:3px;background:linear-gradient(90deg,{sev_color} 0%,{sev_color} 28%,#252525 28%,#252525 100%);border-radius:5px;margin:3px 0 14px'></div>", unsafe_allow_html=True)

        metrics = anomaly.get("metrics", {})
        factor_specs = [
            ("Price movement anomaly", "Price movement", "price_change_pct", "%", "2 points", "Latest return compared with the preceding return baseline."),
            ("Volume spike", "Volume spike", "volume_multiple", "×", "2 points", "Latest volume compared with the preceding median volume."),
            ("RSI14 extreme", "High RSI", "rsi14", "", "1 point", "Extreme upward or downward momentum reading."),
            ("Deviation from SMA20", "SMA20 deviation", "sma20_deviation_pct", "%", "1 point", "Distance between latest price and its 20-period average."),
        ]
        triggered = set(anomaly.get("factors", []))
        factor_cols = st.columns(4, gap="small")
        for idx, (title, factor_name, metric_key, unit, points, note) in enumerate(factor_specs):
            active = factor_name in triggered or (title == "RSI14 extreme" and ("High RSI" in triggered or "Low RSI" in triggered))
            value = metrics.get(metric_key)
            if value is None:
                display_value = "—"
            elif unit == "×":
                display_value = f"{float(value):.2f}×"
            elif unit == "%":
                display_value = f"{float(value):+.2f}%" if metric_key != "volume_multiple" else f"{float(value):.2f}×"
            else:
                display_value = f"{float(value):.1f}"
            border_color = RED if active else BORDER
            state_color = RED if active else "#737373"
            state_text = "TRIGGERED" if active else "NOT TRIGGERED"
            with factor_cols[idx]:
                st.markdown(
                    f"<div class='ms-factor' style='border-color:{border_color}'>"
                    f"<div style='display:flex;justify-content:space-between;gap:6px'><div class='ms-factor-title'>{title}</div><div style='font-size:.63rem;color:{state_color};white-space:nowrap'>● {state_text}</div></div>"
                    f"<div class='ms-factor-value' style='color:{state_color if active else '#F5F5F5'}'>{display_value}</div>"
                    f"<div class='ms-factor-note'>{note}</div><div style='font-size:.7rem;color:{state_color};margin-top:10px'>{points}</div></div>",
                    unsafe_allow_html=True,
                )

        st.write("")
        with st.container(border=True):
            expl_col, meta_col = st.columns([4, 1])
            with expl_col:
                st.markdown("**Why was this flagged?**")
                if anomaly.get("explanation"):
                    for explanation in anomaly["explanation"]:
                        st.write(f"• {explanation}")
                else:
                    st.write("No explanation is available for this candle.")
                if sev == "HIGH":
                    st.warning("High severity means multiple configured rules were triggered; it is not a trading recommendation.")
                elif sev == "MEDIUM":
                    st.info("Medium severity: review the individual factor values and thresholds.")
                elif sev == "LOW":
                    st.info("Low severity: one configured condition was triggered.")
                else:
                    st.success("No configured anomaly threshold was breached by the latest candle.")
            with meta_col:
                st.markdown("**Snapshot**")
                st.caption(f"Asset: {symbol}")
                st.caption(f"Timeframe: {current_tf}")
                st.caption(f"Price: {money(latest_close, currency_symbol)}")
                st.caption(f"Candle: {pd.to_datetime(latest_time).strftime('%d %b %H:%M')}")
                if sev != "NORMAL":
                    st.caption("Saved to PostgreSQL" if anomaly_saved else "Already recorded or save unavailable")
        st.caption("Score guide: 0 Normal · 1 Low · 2–3 Medium · 4–6 High. Thresholds are heuristic, not calibrated probabilities.")

        st.markdown("#### Detected events")
        f1, f2, f3 = st.columns([1.2, 1, 1])
        with f1:
            event_symbol = st.selectbox("Asset filter", ["All"] + sorted({v["symbol"] for v in instrument_map.values()}), key="events_symbol")
        with f2:
            event_severity = st.selectbox("Severity filter", ["All", "HIGH", "MEDIUM", "LOW"], key="events_severity")
        with f3:
            event_sort = st.selectbox("Sort", ["Newest first", "Oldest first"], key="events_sort")
        try:
            event_df = get_anomaly_events(symbol=event_symbol, severity=event_severity, limit=100)
            if not event_df.empty:
                if event_sort == "Oldest first":
                    event_df = event_df.iloc[::-1]
                display_df = event_df.rename(columns={
                    "saved_at": "Saved at", "symbol": "Asset", "timeframe": "Timeframe",
                    "candle_time": "Candle time", "price": "Price (INR)", "severity": "Severity",
                    "score": "Score / 6", "factors": "Triggered factors", "explanation": "Explanation",
                })
                st.dataframe(display_df, width="stretch", hide_index=True, height=250)
                st.caption(f"{len(display_df)} persisted event(s) shown · PostgreSQL records")
            else:
                st.info("No saved anomaly events match these filters yet.")
        except Exception as exc:
            st.warning(f"Could not load anomaly history: {exc}")

    # Two history panels side by side.
    st.write("")
    alert_col, history_col = st.columns(2, gap="medium")
    with alert_col:
        with st.container(border=True):
            st.markdown("<div class=\"ms-section\">Alert history</div>", unsafe_allow_html=True)
            st.caption("Persisted market-signal alerts from PostgreSQL")
            try:
                alerts = get_alerts(instrument_id=instrument["id"], limit=15)
                if alerts.empty:
                    st.info("No market signal alerts saved yet.")
                else:
                    st.dataframe(alerts, width="stretch", hide_index=True, height=300)
            except Exception as exc:
                st.warning(f"Could not load alert history: {exc}")
    with history_col:
        with st.container(border=True):
            st.markdown("<div class=\"ms-section\">Anomaly history</div>", unsafe_allow_html=True)
            st.caption("Persisted anomaly detections · separate from the live snapshot")
            try:
                history = get_anomaly_events(symbol=symbol, severity="All", limit=15)
                if history.empty:
                    st.info("No anomaly events have been saved for this asset yet.")
                else:
                    history_view = history.rename(columns={
                        "saved_at": "Saved at", "symbol": "Asset", "timeframe": "Timeframe",
                        "candle_time": "Candle time", "price": "Price (INR)", "severity": "Severity",
                        "score": "Score", "factors": "Factors", "explanation": "Explanation",
                    })
                    st.dataframe(history_view, width="stretch", hide_index=True, height=300)
            except Exception as exc:
                st.warning(f"Could not load anomaly history: {exc}")

    st.markdown("<div class='ms-footer'>MarketScope · Rule-based market analytics · Verify market data and risk independently. Not financial advice.</div>", unsafe_allow_html=True)


try:
    render_dashboard()
except Exception as exc:
    st.error(f"Dashboard error: {exc}")
