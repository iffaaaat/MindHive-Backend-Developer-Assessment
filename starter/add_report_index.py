import sqlite3


DB = "../data/perf.sqlite"


con = sqlite3.connect(DB)

print("Creating report index...")

con.execute(
    """
    CREATE INDEX IF NOT EXISTS
        idx_match_event_tenant_day_latency
    ON match_event (
        tenant_id,
        substr(created_at, 1, 10),
        latency_ms
    )
    """
)

con.commit()
con.close()

print("Done.")