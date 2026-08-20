# Task 4 — Report Performance

## 1. Baseline Estimation

The production report was too slow to run repeatedly over the full reporting window, so I estimated its behaviour using smaller SQLite slices.

I first tried narrowing only the SQL date filter, including:

- one day across all tenants;
- one tenant on one day.

Those were still impractical to iterate against because the correlated subqueries repeatedly scanned large portions of the full `match_event` table.

I therefore built physically smaller database slices containing only the relevant report window plus the previous day required by `repeat_items_prev_day`.

### Measured Original-Query Results

| Window | Report-window match events | Output rows | Runtime |
|---|---:|---:|---:|
| 1 day | 9,568 | 144 | 76.38 s |
| 2 days | 19,378 | 293 | 228.54 s |

Event volume increased by approximately **2.03×**, while runtime increased by approximately **2.99×**.

This showed that the original report did not scale linearly with report-window rows or days. A simple `one-day runtime × number of days` extrapolation would therefore be misleading.

The supplied reference harness reports a full-window baseline of approximately **3,050 seconds (~50.8 minutes)**. I did not reproduce that full baseline directly because doing so would defeat the purpose of the timeboxed measurement approach.

## 2. Diagnosis

`EXPLAIN QUERY PLAN` showed that the production query repeatedly executes correlated scalar subqueries against `match_event`.

Examples included repeated scans such as:

- `SCAN me2`
- `SCAN me4`
- `SCAN me6`
- `SCAN me7`
- `SCAN me8`
- `SCAN me9`

The most expensive metric was `repeat_items_prev_day`, which repeatedly scans previous-day event data and performs correlated existence checks.

I confirmed this with ablation on a one-tenant / one-day slice.

| Query variant | Runtime |
|---|---:|
| Original metric set | > 5 minutes; terminated |
| Without `repeat_items_prev_day` | 3.15 s |
| Without `repeat_items_prev_day` and `lines_accepted` | 2.49 s |
| Without `repeat_items_prev_day` and `accepted_disabled` | 2.67 s |
| Without `repeat_items_prev_day` and `candidates_considered` | 3.17 s |

Approximate incremental costs on this slice were:

- `lines_accepted`: ~0.66 s
- `accepted_disabled`: ~0.48 s
- `candidates_considered`: no measurable improvement outside run-to-run noise

The evidence showed that the main problem was the correlated execution pattern rather than one isolated column.

## 3. Fix

I rewrote the report using set-based aggregation.

The optimized query:

1. aggregates order-line metrics once at tenant/channel/day grain;
2. aggregates channel-level match-event metrics once;
3. aggregates tenant/day match-event metrics once;
4. builds a distinct tenant/day/item set and self-joins it to compute previous-day repeat items;
5. computes nearest-rank p95 latency using a window-function ranking step;
6. joins the smaller aggregate result sets at the end.

This preserves the original report contract while avoiding repeated full scans per output row.

The first rewrite produced:

- **8,666 rows**
- all **13 baseline columns** matching the supplied reference

Its runtime was:

- **16.088 s**

That was approximately a **190× speedup** over the supplied 3,050-second baseline, but it still missed the required 10-second budget.

## 4. Targeted Index

The p95 calculation partitions and sorts by:

- tenant;
- day;
- latency.

The original database only had a `match_event(line_id)` index, so I added one report-oriented expression index:

```sql
CREATE INDEX idx_match_event_tenant_day_latency
ON match_event (
    tenant_id,
    substr(created_at, 1, 10),
    latency_ms
);
```

This index aligned directly with the access pattern used by the percentile calculation.

### Measured Full-Window Result

One five-run measurement produced:

| Metric | Result |
|---|---:|
| Minimum | 9.103 s |
| Median | 9.221 s |
| Maximum | 9.419 s |
| Budget | 10.0 s |
| Result | **PASS** |
| Speedup vs. supplied baseline | **331×** |

A later verification run produced a median of **9.396 s**, also passing the 10-second budget.

Runtime varies slightly between runs, so I treat these as measured samples rather than fixed constants.

All **8,666 rows** continued to match the supplied reference on all **13 original columns**.

## 5. `p95_latency_ms`

I added `p95_latency_ms` as a nearest-rank percentile over the same tenant/day population used for `max_latency_ms`.

The rank is:

```text
ceil(0.95 × N)
```

I independently verified the SQL implementation against a Python nearest-rank calculation.

### Example Verification

| Metric | Result |
|---|---:|
| Tenant | T001 |
| Day | 2026-06-17 |
| Events | 2,656 |
| Nearest-rank position | 2,524 |
| Python p95 | 292 ms |
| SQL p95 | 292 ms |

The independent calculation matched the SQL result.

## 6. What I Did Not Optimise

I did not continue micro-optimising every remaining metric once the full report was correct and consistently inside the required median budget.

For example, `lines_accepted` and `accepted_disabled` had measurable costs in the ablation experiment, but they were not the dominant problem.

I would revisit them if:

- the 10-second budget becomes tighter;
- event volume grows materially;
- report concurrency increases;
- production monitoring shows insufficient performance margin.

## 7. Trade-offs

The final solution adds a report-oriented index to a write-heavy event ledger.

### Benefits

- substantially reduces full-window report latency;
- supports the tenant/day/latency access pattern used for percentile reporting;
- keeps the final report implementation simple and deterministic.

### Costs

- additional storage;
- extra index maintenance on inserts;
- reduced write throughput compared with an unindexed ledger.

I accepted this trade-off because one targeted index was sufficient to bring the correct set-based rewrite below the required median budget.

I did not add speculative indexes because each additional index would increase write amplification.

## 8. Honest Scaling Ceiling

The current solution satisfies today's workload, but I would not expect the same architecture to remain sufficient at **50× data volume**.

The first pressure points would likely be:

- repeated full-window aggregation;
- sorting and window processing for percentile calculation;
- index size and maintenance cost;
- concurrent dashboard reads competing with event-ledger writes.

At much larger scale, I would move away from computing the complete historical report directly from the transactional event ledger on every request.

A likely next architecture would maintain incremental tenant/day aggregates, with latency distributions or mergeable percentile summaries updated as events arrive.

The dashboard would then read a compact reporting table rather than repeatedly scanning raw event history.

I did not build that architecture for this assessment because the measured set-based rewrite plus one targeted index already satisfies the current requirement.