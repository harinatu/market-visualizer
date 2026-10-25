from database import pool

try:
    if pool.closed:
        pool.open(wait=True)

    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT
                i.symbol,
                a.fingerprint,
                COUNT(*) AS duplicate_count
            FROM alerts a
            JOIN instruments i
                ON i.id = a.instrument_id
            GROUP BY i.symbol, a.fingerprint
            HAVING COUNT(*) > 1
        """).fetchall()

        if rows:
            print("Duplicate fingerprint groups found:")
            for row in rows:
                print(row)
        else:
            print("No duplicate fingerprints found per instrument.")

finally:
    if not pool.closed:
        pool.close()