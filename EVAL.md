# Task 3 — Evaluation

## 1. Evaluation Objective

The matcher is evaluated as a **selective decision system**, not as a standard classification problem.

A wrong automatic match is substantially more expensive than an abstention, so the primary objective is:

> Maximise useful automatic-match coverage while keeping automatic-match precision very high.

The system has three internal evaluation outcomes:

- `AUTO` — accept the match automatically;
- `REVIEW` — a plausible candidate exists, but the evidence is not strong enough for automatic action;
- `NO_MATCH` — candidate evidence is too weak to recommend a catalogue item.

`NO_MATCH` corresponds to the required `reject` decision in `predictions.csv`.

The selected operating point is:

| Parameter | Value |
|---|---:|
| Minimum confidence | 0.85 |
| Minimum margin | 0.10 |
| NO_MATCH floor | 0.70 |

On the 420 training lines:

| Metric | Result |
|---|---:|
| AUTO decisions | 99 |
| AUTO correct | 97 |
| AUTO wrong | 2 |
| AUTO precision | 97.98% |
| AUTO coverage | 23.57% |

Of the 99 AUTO decisions:

- 76 came from strong identifier evidence;
- 23 came from lexical/structured matching.

A stricter `0.925 / 0.10` point achieved 100% measured AUTO precision at 18.10% coverage and slightly better literal cost under the supplied labels.

I retained `0.85 / 0.10` because the two additional apparent AUTO errors are both blank-ground-truth rows that manual inspection identified as likely label ambiguities. In production, I would adjudicate those cases before treating either threshold as permanently optimal.

## 2. Reproducible Evaluation

Run the complete evaluation from the repository root:

```bash
python3 run_evaluation.py
```

This executes the main matcher evaluation followed by the per-noise-class analysis.

Additional diagnostic analysis:

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

Latency benchmark:

```bash
python3 benchmark_matcher.py
```

### Final Aggregate Results

Dataset:

| Metric | Result |
|---|---:|
| Total rows | 420 |
| Positive GT | 295 |
| Blank GT | 125 |

Retrieval:

| Metric | Result |
|---|---:|
| Top-1 accuracy | 263 / 295 = 89.15% |
| Top-5 recall | 292 / 295 = 98.98% |

Strong identifiers:

| Metric | Result |
|---|---:|
| Resolved | 76 |
| Correct | 76 |
| Precision | 100% |

Three-way decisions:

| Decision | Count |
|---|---:|
| AUTO | 99 |
| REVIEW | 261 |
| NO_MATCH | 60 |

AUTO quality:

| Metric | Result |
|---|---:|
| Correct | 97 |
| Wrong | 2 |
| Precision | 97.98% |
| Coverage | 23.57% |

REVIEW composition:

| Type | Count |
|---|---:|
| Positive GT | 195 |
| Blank GT | 66 |

NO_MATCH quality:

| Metric | Result |
|---|---:|
| Correct blank GT | 57 |
| Wrong positive GT | 3 |
| Precision | 95.00% |
| Blank-GT recall | 45.60% |

## 3. Per-Tenant Results

### ACME

| Metric | Result |
|---|---:|
| Rows | 260 |
| Positive GT | 174 |
| Blank GT | 86 |
| AUTO | 57 |
| AUTO correct | 55 |
| AUTO wrong | 2 |
| AUTO precision | 96.49% |
| AUTO coverage | 21.92% |
| REVIEW | 164 |
| NO_MATCH | 39 |

### Nordic

| Metric | Result |
|---|---:|
| Rows | 160 |
| Positive GT | 121 |
| Blank GT | 39 |
| AUTO | 42 |
| AUTO correct | 42 |
| AUTO wrong | 0 |
| AUTO precision | 100% |
| AUTO coverage | 26.25% |
| REVIEW | 97 |
| NO_MATCH | 21 |

No cross-tenant violations were observed.

## 4. Precision Versus Coverage

Accuracy alone is misleading because the business cost of a wrong automatic match is much higher than the cost of review.

The following sweep varies the confidence and margin thresholds:

| Min confidence | Min margin | AUTO | Correct | Wrong | Precision | Coverage |
|---:|---:|---:|---:|---:|---:|---:|
| 0.85 | 0.00 | 268 | 221 | 47 | 82.46% | 63.81% |
| 0.85 | 0.01 | 242 | 221 | 21 | 91.32% | 57.62% |
| 0.85 | 0.03 | 224 | 213 | 11 | 95.09% | 53.33% |
| 0.85 | 0.05 | 211 | 201 | 10 | 95.26% | 50.24% |
| 0.85 | 0.10 | 99 | 97 | 2 | 97.98% | 23.57% |
| 0.90 | 0.00 | 222 | 175 | 47 | 78.83% | 52.86% |
| 0.90 | 0.03 | 182 | 171 | 11 | 93.96% | 43.33% |
| 0.90 | 0.05 | 171 | 161 | 10 | 94.15% | 40.71% |
| 0.90 | 0.10 | 87 | 85 | 2 | 97.70% | 20.71% |
| 0.925 | 0.10 | 76 | 76 | 0 | 100.00% | 18.10% |

Removing the margin requirement increases AUTO coverage from 23.57% to 63.81%, but AUTO precision falls from 97.98% to 82.46%.

This shows why I do not automatically accept the top-ranked candidate even when its score is high. Candidate separation matters.

The `0.925 / 0.10` point is a legitimate safer alternative. Under a literal application of the supplied labels it has slightly better measured cost, but the difference is driven by the two disputed blank-GT rows discussed below.

## 5. Noise-Class Analysis

I defined noise classes from patterns observed in the supplied order lines.

| Noise class | Rows | Positive GT | Blank GT | Top-1 accuracy | Top-5 recall | AUTO precision | AUTO coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| numeric_attributes | 357 | 266 | 91 | 92.86% | 99.25% | 97.37% | 21.29% |
| measurement_text | 269 | 203 | 66 | 93.60% | 99.51% | 96.83% | 23.42% |
| has_uom | 215 | 147 | 68 | 90.48% | 98.64% | 95.56% | 20.93% |
| has_price | 184 | 167 | 17 | 94.01% | 99.40% | 98.15% | 29.35% |
| conversational_noise | 68 | 57 | 11 | 91.23% | 96.49% | 100.00% | 22.06% |
| has_buyer_sku | 64 | 64 | 0 | 59.38% | 95.31% | 100.00% | 100.00% |
| short_text | 51 | 24 | 27 | 41.67% | 95.83% | 100.00% | 47.06% |
| separator_noise | 48 | 40 | 8 | 100.00% | 100.00% | 85.71% | 29.17% |
| spacing_noise | 20 | 19 | 1 | 89.47% | 94.74% | 100.00% | 15.00% |
| has_barcode | 13 | 13 | 0 | 61.54% | 100.00% | 100.00% | 92.31% |
| plain_text | 7 | 1 | 6 | 100.00% | 100.00% | 0.00% | 0.00% |

Several patterns matter.

First, top-5 recall remains high even where top-1 accuracy is weaker. Candidate generation is therefore usually successful; many remaining failures are ranking or ambiguity problems.

Second, buyer-SKU and barcode rows have weaker lexical top-1 accuracy but very strong AUTO precision because validated identifiers are evaluated before the lexical lane.

Third, short-text rows illustrate why raw top-1 accuracy is misleading. Their lexical top-1 accuracy is only 41.67%, but AUTO precision is 100%. When the description does not contain enough information, the system abstains rather than forcing a lexical answer.

## 6. Manual Error Analysis

I manually inspected specific failures and grouped them into:

1. genuine matcher defects;
2. under-specified text recovered by stronger identifiers;
3. intrinsic catalogue or input ambiguity;
4. likely label problems.

The cost class represents the likely production consequence:

- **High** — could cause an incorrect automatic SKU selection;
- **Medium** — primarily causes unnecessary human review;
- **Data** — the available input or label does not define a unique software fix.

### 6.1 Genuine Matcher Defects Found and Fixed

| line_id | Failure | Root cause | Cost | Fix |
|---|---|---|---|---|
| ACM-T-0071 | `tolsen GRINDING DISC 4.5" flap` initially ranked a generic grinding disc above the GT flap disc | Lexical similarity did not recognise the more specific variant | High | Added variant extraction and reranking |
| ACM-T-0166 | `BOSCO GRINDING DISC 5" FLAP` initially preferred the grinding variant | Same variant-ranking capability gap | High | Covered by the same variant rule and regression test |
| ACM-T-0179 | `Remax Ball Valve " 1PVC` failed to interpret the intended dimension | Inch marker appears before the number | High | Added misplaced-inch normalisation to produce `1in pvc` |
| ACM-T-0249 | `putih` did not match catalogue colour `White` | Missing narrow multilingual normalisation | Medium | Added `putih -> white` |

These fixes are reusable capabilities rather than row-specific ground-truth patches.

### 6.2 Under-Specified Text Recovered by Identifiers

| line_id | Input symptom | Missing information | Identifier evidence | Cost | Production treatment |
|---|---|---|---|---|---|
| ACM-T-0010 | `Vermont GI Wire Soft` | Wire gauge | buyer SKU | Medium | Use alias; otherwise review |
| ACM-T-0011 | `need Kanto Grinder Disc Grinding` | Disc size | buyer SKU | Medium | Use alias; otherwise review |
| ACM-T-0035 | `Stallion Hose Clip Zinc` | Diameter/range | buyer SKU | Medium | Use alias; otherwise review |
| ACM-T-0037 | `Vermont - Valve` | Size and material | buyer SKU | High | Use alias; never invent attributes |
| ACM-T-0091 | `Vermont PVC 32mm Class` | Class letter | barcode | High | Barcode resolves exact SKU |
| ACM-T-0103 | `M6x50 304` | Brand | buyer SKU | Medium | Use alias; otherwise review |
| ACM-T-0105 | `GI Wire #18 Hard` | Brand | buyer SKU | Medium | Use alias; otherwise review |
| ACM-T-0118 | `Plug 12mm Blue` | Brand | barcode | Medium | Barcode resolves exact SKU |
| ACM-T-0132 | `GI Wire` | Brand, gauge and grade | buyer SKU | High | Use alias; lexical AUTO would be unsafe |
| ACM-T-0133 | `urgent Pipe 40mm Class D` | Brand | buyer SKU | Medium | Use alias; otherwise review |
| ACM-T-0186 | `PVC 20mm Class E` | Brand | barcode | Medium | Barcode resolves exact SKU |
| ACM-T-0255 | `urgent Self Drilling Screw #10 x` | Brand, length and finish | buyer SKU | High | Use alias; otherwise review |

These cases should not be “fixed” by inventing defaults such as a preferred brand, size, colour, or class.

### 6.3 Intrinsic Ambiguity

| line_id | Problem | Root cause | Cost | Production treatment |
|---|---|---|---|---|
| ACM-T-0209 | `Masking Tape 24mm High Temp` does not identify the labelled Bulk/Tolsen SKU | Brand and Bulk information are missing | Data | Keep multiple candidates and review |
| NRD-T-0009 | `Golden Pantry Full Cream Milk UHT 200ml` has base and Bulk catalogue twins | Visible evidence and barcode do not safely distinguish them | Data | Review unless stronger context exists |

I tested whether absence of the word `Bulk` could safely imply the base item. The training data contains examples in both directions, so I rejected that heuristic.

### 6.4 Likely Label or Task Ambiguity

| line_id | Issue | Why questionable | Production treatment |
|---|---|---|---|
| ACM-T-0177 | Exact visible product match but GT is blank | Main discrepancy is unit-like order UOM versus catalogue `Packet` UOM | Flag for data review; do not introduce a hard UOM rejection |
| ACM-T-0212 | Same pattern: exact visible match but GT is blank | Positive labelled rows show unit-to-packet mappings can be valid | Flag for data review |
| ACM-T-0209 | Label chooses a specific Bulk/Tolsen item | Input does not contain enough information to justify that unique choice | Review unless stronger context exists |
| NRD-T-0009 | GT chooses the base item | Base and Bulk twins are indistinguishable from the supplied evidence | Review or improve catalogue contract |

These examples identify questionable or under-specified labels rather than blindly optimising against them.

In production, I would keep disputed labels separate until an operator or catalogue owner adjudicates them.

## 7. When I Stopped Tuning

After the targeted fixes, there were 32 remaining positive-GT lexical top-1 disagreements.

Of those:

- 30 were correctly resolved by the identifier lane;
- 0 identifier resolutions were incorrect;
- 0 barcode/alias conflicts occurred;
- only 2 had no unique identifier resolution, and both were intrinsically ambiguous or under-specified.

At that point I stopped adding lexical heuristics.

Further tuning would mainly teach arbitrary catalogue preferences rather than improve generalisation.

## 8. Regression Safety

The evaluation harness should prevent unsafe matcher changes from shipping.

### Hard Correctness Gates

Fail immediately on:

- any cross-tenant prediction;
- any incorrect strong-identifier resolution;
- duplicate or invalid rows in `predictions.csv`;
- confidence outside `[0,1]`;
- normalisation or variant regression-test failure;
- p95 matcher latency above 250 ms.

### AUTO Precision Gate

Current reference:

- minimum confidence: `0.85`;
- minimum margin: `0.10`;
- AUTO precision: `97.98%`;
- AUTO coverage: `23.57%`.

A practical release gate would require:

- AUTO precision >= 97%;
- zero new incorrect strong-identifier resolutions.

Coverage may increase only if the precision floor remains satisfied.

### Retrieval Gate

Candidate generation should also be monitored separately.

I would fail or investigate a change if:

- positive-GT top-5 recall materially decreases;
- a GT item previously present in the top 20 disappears entirely.

### Benchmark Maintenance

To avoid benchmark rot:

1. version evaluation data and matcher configuration together;
2. keep historical metrics per release;
3. add adjudicated production failures to the regression set;
4. monitor by tenant and noise class;
5. keep disputed labels separate until resolved.

## 9. Latency

Latest verification run:

| Metric | Latency |
|---|---:|
| Average | 5.923 ms |
| P50 | 6.741 ms |
| P95 | 9.344 ms |
| P99 | 10.392 ms |
| Maximum | 17.629 ms |

The measured p95 remains comfortably below the required 250 ms per-line budget.

## 10. Conclusion

The main result is not a single accuracy number.

The matcher deliberately separates:

- candidate retrieval;
- strong identifier evidence;
- structured ranking;
- confidence calibration;
- automation versus abstention.

At the selected operating point it achieves **97.98% AUTO precision at 23.57% AUTO coverage**, while positive-GT top-5 recall remains **98.98%**.

Manual error analysis showed that many remaining lexical disagreements are under-specified descriptions, catalogue ambiguities, or questionable labels rather than reusable matcher defects.

For that reason, I stopped tuning when additional rules no longer had clear evidence that they would generalise.