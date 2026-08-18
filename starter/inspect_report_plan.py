import sqlite3


DB = "../data/perf.sqlite"
SQL_FILE = "one_tenant_one_day.sql"


con = sqlite3.connect(DB)

sql = open(
    SQL_FILE,
    encoding="utf-8",
).read()


print("=== EXISTING INDEXES ===")

for table in [
    "order_line",
    "match_event",
    "item",
    "tenant",
]:

    print()
    print(f"[{table}]")

    indexes = con.execute(
        f"PRAGMA index_list('{table}')"
    ).fetchall()

    if not indexes:
        print("  none")
        continue

    for index in indexes:
        print(" ", index)


print()
print("=== QUERY PLAN ===")

plan = con.execute(
    "EXPLAIN QUERY PLAN " + sql
).fetchall()

for row in plan:
    print(row)


con.close()