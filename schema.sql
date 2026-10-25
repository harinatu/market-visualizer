CREATE TABLE IF NOT EXISTS instruments (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    asset_type VARCHAR(20) NOT NULL,
    exchange VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS candles (
    id BIGSERIAL PRIMARY KEY,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id),
    timeframe VARCHAR(5) NOT NULL,
    candle_time TIMESTAMPTZ NOT NULL,
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(30, 8) NOT NULL DEFAULT 0,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (instrument_id, timeframe, candle_time)
);

CREATE INDEX IF NOT EXISTS idx_candles_history
ON candles (instrument_id, timeframe, candle_time DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal VARCHAR(20) NOT NULL,
    evidence_strength VARCHAR(20) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    timeframe VARCHAR(5) NOT NULL DEFAULT '15m',
    price NUMERIC(20, 8) NOT NULL,
    explanation TEXT NOT NULL,
    invalidation TEXT NOT NULL,
    fingerprint VARCHAR(150) NOT NULL,
    UNIQUE (instrument_id, fingerprint)
);

-- Safe migration for databases created before timeframe was added.
ALTER TABLE alerts
ADD COLUMN IF NOT EXISTS timeframe VARCHAR(5) NOT NULL DEFAULT '15m';

INSERT INTO instruments (symbol, name, asset_type, exchange)
VALUES
    ('BTCUSDT', 'Bitcoin', 'crypto', 'Binance'),
    ('ETHUSDT', 'Ethereum', 'crypto', 'Binance'),
    ('DOGEUSDT', 'Dogecoin', 'crypto', 'Binance'),
    ('RELIANCE', 'Reliance Industries', 'stock', 'NSE'),
    ('TCS', 'Tata Consultancy Services', 'stock', 'NSE'),
    ('HDFCBANK', 'HDFC Bank', 'stock', 'NSE')
ON CONFLICT (symbol) DO NOTHING;

CREATE TABLE IF NOT EXISTS anomaly_events (
    id BIGSERIAL PRIMARY KEY,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id),
    symbol VARCHAR(30) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    candle_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price NUMERIC(20, 8) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    score INTEGER NOT NULL,
    factors TEXT NOT NULL,
    explanation TEXT NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (instrument_id, timeframe, candle_time)
);

CREATE INDEX IF NOT EXISTS idx_anomaly_events_recent
ON anomaly_events (candle_time DESC);
