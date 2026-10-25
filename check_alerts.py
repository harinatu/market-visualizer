from database import pool

try:
    if pool.closed:
        pool.open(wait=True)

    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT
                i.symbol,
                a.signal,
                a.evidence_strength,
                a.risk_level,
                a.price,
                a.created_at,
                a.fingerprint
            FROM alerts a
            JOIN instruments i ON i.id = a.instrument_id
            ORDER BY a.created_at DESC
            LIMIT 20
        """).fetchall()

        print("\n=== RECENT ALERTS ===")

        if not rows:
            print("No alerts have been recorded yet.")
        else:
            for row in rows:
                print("-" * 45)
                print(f"Symbol: {row[0]}")
                print(f"Signal: {row[1]}")
                print(f"Evidence: {row[2]}")
                print(f"Risk: {row[3]}")
                print(f"Price: {row[4]}")
                print(f"Created: {row[5]}")
                print(f"Fingerprint: {row[6]}")

finally:
    if not pool.closed:
        pool.close()