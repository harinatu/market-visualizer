from database import pool

try:
    if pool.closed:
        pool.open(wait=True)

    query = """
        SELECT
            i.symbol,
            COUNT(c.id) AS candle_count,
            MAX(c.candle_time) AS latest_candle,
            EXTRACT(
                EPOCH FROM (NOW() - MAX(c.candle_time))
            ) AS age_seconds
        FROM instruments i
        LEFT JOIN candles c
            ON c.instrument_id = i.id
            AND c.timeframe = '1m'
        WHERE i.symbol IN ('BTCUSDT', 'ETHUSDT', 'DOGEUSDT')
        GROUP BY i.symbol
        ORDER BY i.symbol;
    """

    with pool.connection() as conn:
        rows = conn.execute(query).fetchall()

    print("\n=== CRYPTO FEED HEALTH CHECK ===")

    for symbol, count, latest, age in rows:
        print(f"\nSymbol: {symbol}")
        print(f"Stored candles: {count}")
        print(f"Latest candle: {latest}")

        if age is None:
            print("Status: NO DATA")
        else:
            print(f"Data age: {age:.1f} seconds")

            if age <= 120:
                print("Status: RECENT")
            else:
                print("Status: STALE")

finally:
    if not pool.closed:
        pool.close()