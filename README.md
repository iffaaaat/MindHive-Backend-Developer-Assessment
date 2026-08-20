# MindHive Backend Developer Assessment

This repository contains my submission for the MindHive Backend Developer technical assessment.

## Requirements

- Python 3.10+
- `rapidfuzz`

Install the only external Python dependency:

```bash
python3 -m pip install rapidfuzz
```

All other delivered code uses the Python standard library and SQLite. No network access is required.

## Deliverables

| File | Purpose |
|---|---|
| `DESIGN.md` | Task 1 — problem framing and design |
| `predictions.csv` | Task 2 — holdout predictions |
| `EVAL.md` | Task 3 — evaluation and error analysis |
| `PERF.md` | Task 4 — report performance investigation |
| `SYNC.md` | Task 5 — ERP sync debugging |
| `SCALE.md` | Task 6 — scale and rollout |
| `DECISIONS.md` | decision log for major engineering choices |

Core implementation:

```text
src/                    matcher implementation
evaluation/             evaluation modules
starter/                Task 4 starter/report solution
starter/sync/           Task 5 ERP sync
analysis_tools/         supporting investigation scripts
```

---

## Task 2 — Matcher

Generate the holdout predictions from the repository root:

```bash
python3 generate_predictions.py
```

Validate the output:

```bash
python3 validate_predictions.py
```

Expected validation:

```text
rows: 300
unique line_ids: 300
errors: 0

PASS: exactly 300 prediction rows
PASS: schema and row-level validation succeeded
```

The output schema is:

```text
line_id,item_code,confidence,decision,reason_code,candidates
```

The matcher implementation is under `src/`, primarily `src/matcher.py`.

---

## Task 3 — Evaluation

Run the complete evaluation harness from the repository root:

```bash
python3 run_evaluation.py
```

This runs the main matcher evaluation followed by the per-noise-class analysis.

It reports:

- aggregate retrieval and decision metrics;
- per-tenant AUTO quality;
- strong-identifier performance;
- AUTO precision and coverage;
- REVIEW and NO_MATCH composition;
- residual AUTO errors;
- per-noise-class retrieval and decision metrics.

Additional diagnostic evaluation:

```bash
python3 evaluate_three_way.py
python3 evaluate_decisions.py
```

Regression checks:

```bash
python3 test_baseline.py
python3 test_normalizer.py
python3 test_matcher_variants.py
```

Matcher latency benchmark:

```bash
python3 benchmark_matcher.py
```

Current selected operating point:

| Parameter | Value |
|---|---:|
| Minimum confidence | 0.85 |
| Minimum margin | 0.10 |
| NO_MATCH floor | 0.70 |
| AUTO precision | 97.98% |
| AUTO coverage | 23.57% |

The matcher remains comfortably below the required 250 ms p95 per-line budget.

Detailed metrics, operating-point analysis, manual failure analysis, label ambiguity, and release gates are documented in `EVAL.md`.

---

## Task 4 — Report Performance

Task 4 uses a generated SQLite database.

From the repository root:

```bash
cd starter
```

Build the database:

```bash
python3 make_perf_db.py --out ../data/perf.sqlite
```

Add the report-oriented index:

```bash
python3 add_report_index.py
```

Run the optimized full-window report check:

```bash
python3 bench_report.py check \
    --db ../data/perf.sqlite \
    --sql my_report.sql \
    --repeat 5 \
    --budget-s 10
```

The final query:

- produces 8,666 rows;
- matches all 13 supplied baseline columns;
- adds `p95_latency_ms`;
- passes the 10-second median budget.

Verify the p95 calculation independently:

```bash
python3 verify_p95.py
```

Expected verification:

```text
Python p95: 292
SQL p95: 292

PASS: SQL p95 matches independent nearest-rank calculation
```

Return to the repository root:

```bash
cd ..
```

The baseline estimation, diagnosis, ablation work, rewrite, index trade-off, and scaling ceiling are documented in `PERF.md`.

---

## Task 5 — ERP Sync

From the repository root:

```bash
cd starter/sync
```

Run the isolated regression tests:

```bash
python3 -m unittest test_sync_adapter.py -v
```

Expected result:

```text
Ran 9 tests

OK
```

Run the supplied scenario:

```bash
python3 run_sync.py
```

Expected result:

```text
pulled=60 pushed=2 remote=60 local=60

all invariants hold for this scenario (that is not the same as the adapter being correct)
```

Return to the repository root:

```bash
cd ../..
```

`starter/sync/fake_erp.py` is the supplied vendor simulator and was not modified.

The defect list, regression tests, invariants, crash-safety behaviour, vendor-contract requests, and scale risks are documented in `SYNC.md`.

---

## Supporting Analysis

`analysis_tools/` contains supporting scripts used during matcher failure analysis and Task 4 performance investigation.

Generated databases, benchmark slices, Python caches, and other local working artifacts are excluded from Git.