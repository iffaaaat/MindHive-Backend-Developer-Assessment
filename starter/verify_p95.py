import math
import sqlite3


DB = "../data/perf.sqlite"


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row


# Pick one tenant/day that has match events.
sample = con.execute(
    """
    SELECT
        tenant_id,
        substr(created_at, 1, 10) AS day,
        COUNT(*) AS n
    FROM match_event
    WHERE substr(created_at, 1, 10)
          BETWEEN '2026-05-01' AND '2026-06-30'
    GROUP BY
        tenant_id,
        substr(created_at, 1, 10)
    ORDER BY n DESC
    LIMIT 1
    """
).fetchone()


tenant_id = sample["tenant_id"]
day = sample["day"]


latencies = [
    row["latency_ms"]
    for row in con.execute(
        """
        SELECT latency_ms
        FROM match_event
        WHERE tenant_id = ?
          AND substr(created_at, 1, 10) = ?
        ORDER BY latency_ms
        """,
        (tenant_id, day),
    )
]


# Independent Python nearest-rank calculation.
rank = math.ceil(0.95 * len(latencies))
python_p95 = latencies[rank - 1]


# Same SQL method used by my_report.sql.
sql_p95 = con.execute(
    """
    WITH ranked AS (
        SELECT
            latency_ms,

            ROW_NUMBER() OVER (
                ORDER BY latency_ms
            ) AS rn,

            COUNT(*) OVER () AS cnt

        FROM match_event

        WHERE tenant_id = ?
          AND substr(created_at, 1, 10) = ?
    )

    SELECT MAX(
        CASE
            WHEN rn = ((cnt * 95 + 99) / 100)
            THEN latency_ms
        END
    ) AS p95_latency_ms

    FROM ranked
    """,
    (tenant_id, day),
).fetchone()["p95_latency_ms"]


print("=== P95 VERIFICATION ===")
print("tenant:", tenant_id)
print("day:", day)
print("events:", len(latencies))
print("nearest-rank position:", rank)
print("Python p95:", python_p95)
print("SQL p95:", sql_p95)
print()


assert python_p95 == sql_p95, (
    f"P95 mismatch: Python={python_p95}, SQL={sql_p95}"
)

print("PASS: SQL p95 matches independent nearest-rank calculation")


con.close()