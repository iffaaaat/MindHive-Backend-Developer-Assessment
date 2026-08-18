import sqlite3
from pathlib import Path


SOURCE_DB = "../data/perf.sqlite"


SLICES = [
    (
        "perf_slice_1d.sqlite",
        "2026-05-01",
        "2026-05-01",
    ),
    (
        "perf_slice_2d.sqlite",
        "2026-05-01",
        "2026-05-02",
    ),
    (
        "perf_slice_4d.sqlite",
        "2026-05-01",
        "2026-05-04",
    ),
]


def copy_rows(
    src,
    dst,
    table,
    where_clause="",
    params=(),
):
    query = f"SELECT * FROM {table}"

    if where_clause:
        query += f" WHERE {where_clause}"

    rows = src.execute(
        query,
        params,
    ).fetchall()

    if not rows:
        return 0

    columns = rows[0].keys()

    placeholders = ",".join(
        "?" for _ in columns
    )

    dst.executemany(
        f"""
        INSERT INTO {table}
        VALUES ({placeholders})
        """,
        [
            tuple(
                row[column]
                for column in columns
            )
            for row in rows
        ],
    )

    return len(rows)


def build_slice(
    output_path,
    date_from,
    date_to,
):
    output = Path(output_path)

    if output.exists():
        output.unlink()

    src = sqlite3.connect(SOURCE_DB)
    dst = sqlite3.connect(output_path)

    src.row_factory = sqlite3.Row


    # --------------------------------------------------
    # Copy table schema only.
    # --------------------------------------------------

    tables = src.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND sql IS NOT NULL
        """
    ).fetchall()

    for row in tables:
        dst.execute(row["sql"])


    # --------------------------------------------------
    # Copy small reference tables completely.
    # --------------------------------------------------

    copy_rows(
        src,
        dst,
        "tenant",
    )

    copy_rows(
        src,
        dst,
        "item",
    )


    # --------------------------------------------------
    # Copy report-window order lines.
    # --------------------------------------------------

    copy_rows(
        src,
        dst,
        "order_line",
        """
        substr(created_at, 1, 10) >= ?
        AND substr(created_at, 1, 10) <= ?
        """,
        (
            date_from,
            date_to,
        ),
    )


    # --------------------------------------------------
    # match_event needs the previous day as well because
    # repeat_items_prev_day checks current vs previous day.
    # --------------------------------------------------

    previous_day = src.execute(
        """
        SELECT date(?, '-1 day')
        """,
        (date_from,),
    ).fetchone()[0]


    copy_rows(
        src,
        dst,
        "match_event",
        """
        substr(created_at, 1, 10) >= ?
        AND substr(created_at, 1, 10) <= ?
        """,
        (
            previous_day,
            date_to,
        ),
    )


    # --------------------------------------------------
    # Restore original indexes only.
    # Do NOT copy our experimental report index.
    # --------------------------------------------------

    indexes = src.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'index'
          AND sql IS NOT NULL
          AND name != 'idx_match_event_tenant_day_latency'
        """
    ).fetchall()

    for row in indexes:
        dst.execute(row["sql"])


    dst.commit()


    line_count = dst.execute(
        """
        SELECT COUNT(*)
        FROM order_line
        """
    ).fetchone()[0]

    event_count = dst.execute(
        """
        SELECT COUNT(*)
        FROM match_event
        """
    ).fetchone()[0]

    report_event_count = dst.execute(
        """
        SELECT COUNT(*)
        FROM match_event
        WHERE substr(created_at, 1, 10) >= ?
          AND substr(created_at, 1, 10) <= ?
        """,
        (
            date_from,
            date_to,
        ),
    ).fetchone()[0]


    print(
        f"{output_path}: "
        f"{date_from} to {date_to} | "
        f"{line_count} lines | "
        f"{event_count} stored events | "
        f"{report_event_count} report-window events"
    )


    src.close()
    dst.close()


for (
    output_path,
    date_from,
    date_to,
) in SLICES:

    build_slice(
        output_path,
        date_from,
        date_to,
    )