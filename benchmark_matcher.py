import math
import time

from src.data_loader import load_training_lines
from src.matcher import Matcher


REPEATS = 10


def percentile_nearest_rank(values, percentile):
    values = sorted(values)

    rank = math.ceil(
        percentile / 100 * len(values)
    )

    return values[rank - 1]


matcher = Matcher()
rows = load_training_lines()


# ---------------------------------------------------------
# Warm-up
#
# The assessment explicitly excludes cold-cache/startup cost
# from the <= 250 ms p95 per-line requirement.
# ---------------------------------------------------------

for line in rows:
    matcher.decide(line)


# ---------------------------------------------------------
# Benchmark
# ---------------------------------------------------------

latencies_ms = []

for _ in range(REPEATS):

    for line in rows:

        start = time.perf_counter()

        matcher.decide(line)

        elapsed_ms = (
            time.perf_counter() - start
        ) * 1000

        latencies_ms.append(elapsed_ms)


# ---------------------------------------------------------
# Results
# ---------------------------------------------------------

average_ms = sum(latencies_ms) / len(latencies_ms)

p50_ms = percentile_nearest_rank(
    latencies_ms,
    50,
)

p95_ms = percentile_nearest_rank(
    latencies_ms,
    95,
)

p99_ms = percentile_nearest_rank(
    latencies_ms,
    99,
)

max_ms = max(latencies_ms)


print("=== MATCHER LATENCY BENCHMARK ===")
print("rows:", len(rows))
print("repeats:", REPEATS)
print("decisions measured:", len(latencies_ms))
print()
print("average ms:", round(average_ms, 3))
print("p50 ms:", round(p50_ms, 3))
print("p95 ms:", round(p95_ms, 3))
print("p99 ms:", round(p99_ms, 3))
print("max ms:", round(max_ms, 3))
print()

if p95_ms <= 250:
    print(
        "PASS: p95 is within the "
        "<= 250 ms per-line budget."
    )
else:
    print(
        "FAIL: p95 exceeds the "
        "<= 250 ms per-line budget."
    )