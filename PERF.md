# Task 4 — Report Performance

## 1. Baseline Estimation

The production report was too slow to run repeatedly over the full reporting window, so I estimated its behaviour using physically smaller SQLite slices.

I first tried narrowing only the SQL date filter, including:

* one day across all tenants;
* one tenant on one day.

Both approaches were still impractical to iterate against because the correlated subqueries repeatedly scanned large portions of the full `match_event` table.

I therefore built physical database slices containing only the relevant report window plus the previous day required by the `repeat_items_prev_day` metric.

### Measured Original-Query Results

| Window | Report-window match events | Output rows |  Runtime |
| ------ | -------------------------: | ----------: | -------: |
| 1 day  |                      9,568 |         144 |  76.38 s |
| 2 days |                     19,378 |         293 | 228.54 s |

The event volume increased by approximately **2.03×**, while runtime increased by approximately **2.99×**.

This shows that the original report does not scale linearly with report-window rows or days. A simple `one-day runtime × number of days` extrapolation would therefore be misleading.

The supplied reference harness reports a full-window baseline of approximately **3,050 seconds (~50.8 minutes)**. I did not reproduce that full baseline directly because doing so would defeat the purpose of the timeboxed measurement approach.

## 2. Diagnosis

`EXPLAIN QUERY PLAN` showed that the production query repeatedly executes correlated scalar subqueries against `match_event`.

Examples from the query plan included repeated:

* `SCAN me2`
* `SCAN me4`
* `SCAN me6`
* `SCAN me7`
* `SCAN me8`
* `SCAN me9`

The most expensive-looking metric was `repeat_items_prev_day`, which performs a scan of `match_event me8` followed by a correlated `EXISTS` lookup against `match_event me9`.

I tested this empirically using a one-tenant / one-day slice.

| Query variant                                               |                 Runtime |
| ----------------------------------------------------------- | ----------------------: |
| Original metric set                                         | > 5 minutes; terminated |
| Without `repeat_items_prev_day`                             |                  3.15 s |
| Without `repeat_items_prev_day` and `lines_accepted`        |                  2.49 s |
| Without `repeat_items_prev_day` and `accepted_disabled`     |                  2.67 s |
| Without `repeat_items_prev_day` and `candidates_considered` |                  3.17 s |

The dominant cost was therefore `repeat_items_prev_day`.

Approximate incremental costs on this slice were:

* `lines_accepted`: ~0.66 s
* `accepted_disabled`: ~0.48 s
* `candidates_considered`: no measurable improvement within run-to-run noise

The evidence suggested that the correct fix was not to micro-optimise each correlated subquery independently, but to remove the correlated execution pattern entirely.

## 3. Fix

I rewrote the report using set-based aggregation.

The optimized query:

1. Aggregates order-line metrics once at tenant/channel/day grain.
2. Aggregates channel-level match-event metrics once.
3. Aggregates tenant/day match-event metrics once.
4. Builds a distinct tenant/day/item set and self-joins it to compute previous-day repeat items.
5. Computes nearest-rank p95 latency using a window-function ranking step.
6. Joins the small aggregate result sets together at the end.

This preserves the original report contract while avoiding repeated full scans per output row.

The first rewrite produced byte-equivalent results on all original columns:

* **8,666 rows**
* all **13 baseline columns** matched the supplied reference

However, it took:

* **16.088 s**

This represented a **190× speedup** over the supplied 3,050 s baseline, but still missed the required 10-second target.

## 4. Targeted Index

The p95 calculation partitions and sorts by:

* tenant
* day
* latency

The original database only had a `match_event(line_id)` index, so I added one report-oriented expression index:

```sql
CREATE INDEX idx_match_event_tenant_day_latency
ON match_event (
    tenant_id,
    substr(created_at, 1, 10),
    latency_ms
);
```

After adding this index, the full-window report passed the required budget.

### Five-Run Measurement

| Metric                        |   Result |
| ----------------------------- | -------: |
| Minimum                       |  9.103 s |
| Median                        |  9.221 s |
| Maximum                       |  9.419 s |
| Budget                        |   10.0 s |
| Result                        | **PASS** |
| Speedup vs. supplied baseline | **331×** |

All **8,666 rows** continued to match the supplied reference on all **13 original columns**.

## 5. `p95_latency_ms`

I added `p95_latency_ms` as a nearest-rank percentile over the same tenant/day population used for `max_latency_ms`.

The rank is:

```text
ceil(0.95 × N)
```

I independently verified the SQL implementation against a Python nearest-rank calculation.

### Example Verification

| Metric                |     Result |
| --------------------- | ---------: |
| Tenant                |       T001 |
| Day                   | 2026-06-17 |
| Events                |      2,656 |
| Nearest-rank position |      2,524 |
| Python p95            |     292 ms |
| SQL p95               |     292 ms |

The independent calculation matched the SQL result.

## 6. What I Did Not Optimise

I did not continue micro-optimising every remaining report metric after the full report was correct and consistently inside the 10-second budget.

For example, `lines_accepted` and `accepted_disabled` had measurable costs in the ablation experiment, but they were not the dominant problem.

Further optimisation would have increased implementation complexity for relatively small gains under the current requirement.

I would revisit those components if:

* the 10-second budget becomes tighter;
* event volume grows materially;
* report concurrency increases; or
* production monitoring shows that the current performance margin is insufficient.

## 7. Trade-offs

The final solution adds a report-oriented index to a write-heavy event ledger.

### Benefits

* Substantially reduces full-window report latency.
* Supports the tenant/day/latency access pattern used for percentile reporting.
* Keeps the report implementation simple and deterministic.

### Costs

* Additional storage.
* Extra index maintenance on inserts.
* Reduced write throughput compared with an unindexed ledger.

This matters because the ledger receives many writes per order line.

I accepted this trade-off because one targeted index was sufficient to move the correct set-based rewrite from **16.088 s** to a stable median of **9.221 s**.

I did not add a collection of speculative indexes because every additional index would increase write amplification.

## 8. Honest Scaling Ceiling

The current solution satisfies today's workload, but I would not expect the same architecture to remain sufficient at **50× data volume**.

The first pressure points would likely be:

* repeated full-window aggregation;
* sorting and window processing required for percentile calculation;
* index size and maintenance cost;
* concurrent dashboard reads competing with event-ledger writes.

At much larger scale, I would move away from computing the complete historical report directly from the transactional event ledger on every request.

A likely next architecture would maintain incremental tenant/day aggregates, with latency distributions or mergeable percentile summaries generated as events arrive.

The dashboard would then read a compact reporting table rather than repeatedly scanning the raw event ledger.

I did not build that architecture for this assessment because the measured set-based rewrite plus one targeted index already satisfies the current **10-second requirement**. Building materialisation now would introduce freshness, migration, and operational complexity before the evidence requires it.
