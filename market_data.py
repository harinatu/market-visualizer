import asyncio
import json
import time
from datetime import datetime, timezone

import requests
import websockets

from database import (
    pool,
    initialize_database,
    get_instruments,
    save_candle,
)

CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "DOGEUSDT"]

REST_URL = "https://api.binance.com/api/v3/klines"
WS_URL = (
    "wss://stream.binance.com:9443/stream?streams="
    + "/".join(f"{s.lower()}@kline_1m" for s in CRYPTO_SYMBOLS)
)

instrument_ids = {}


def load_instrument_ids():
    global instrument_ids

    rows = get_instruments()
    instrument_ids = {
        row[1]: row[0]
        for row in rows
        if row[1] in CRYPTO_SYMBOLS
    }

    missing = set(CRYPTO_SYMBOLS) - set(instrument_ids)
    if missing:
        raise RuntimeError(
            f"Missing instruments in PostgreSQL: {sorted(missing)}"
        )


def backfill_history():
    """Load recent 1-minute candles before starting the live stream."""
    for symbol in CRYPTO_SYMBOLS:
        print(f"Loading recent history for {symbol}...")

        response = requests.get(
            REST_URL,
            params={"symbol": symbol, "interval": "1m", "limit": 500},
            timeout=20,
        )
        response.raise_for_status()

        for item in response.json():
            candle_time = datetime.fromtimestamp(
                item[0] / 1000, tz=timezone.utc
            )
            save_candle(
                instrument_ids[symbol],
                candle_time,
                float(item[1]),
                float(item[2]),
                float(item[3]),
                float(item[4]),
                float(item[5]),
                is_closed=(item[6] < int(time.time() * 1000)),
            )

        print(f"History loaded for {symbol}.")


async def stream_market_data():
    while True:
        try:
            print("Connecting to Binance WebSocket...")

            async with websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            ) as websocket:
                print("Connected. Receiving live crypto candles.")

                async for message in websocket:
                    payload = json.loads(message)
                    candle = payload.get("data", {}).get("k")

                    if not candle:
                        continue

                    symbol = candle["s"]
                    if symbol not in instrument_ids:
                        continue

                    candle_time = datetime.fromtimestamp(
                        candle["t"] / 1000, tz=timezone.utc
                    )

                    save_candle(
                        instrument_ids[symbol],
                        candle_time,
                        float(candle["o"]),
                        float(candle["h"]),
                        float(candle["l"]),
                        float(candle["c"]),
                        float(candle["v"]),
                        is_closed=bool(candle["x"]),
                    )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Market feed disconnected: {exc}")
            print("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


async def main():
    pool.open(wait=True)

    try:
        initialize_database()
        load_instrument_ids()
        backfill_history()
        await stream_market_data()
    finally:
        pool.close()


if __name__ == "__main__":
    asyncio.run(main())