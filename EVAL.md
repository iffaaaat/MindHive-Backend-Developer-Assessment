# Evaluation

## 1. Evaluation Objective

The matcher is evaluated as a **selective decision system** rather than as a standard classification problem.

A wrong automatic match is substantially more expensive than an abstention, so the primary operating objective is:

> **Maximise useful automatic-match coverage while keeping automatic-match precision very high.**

The system therefore has three possible outcomes:

* `AUTO` — accept the match automatically.
* `REVIEW` — a plausible candidate exists, but the evidence is not strong enough for automatic action.
* `NO_MATCH` — candidate evidence is too weak to recommend a catalogue item.

This distinction is important because raw top-1 accuracy does not capture the business cost of confidently selecting the wrong item.

The selected operating point is:

* **Minimum confidence:** `0.85`
* **Minimum confidence margin:** `0.10`
* **No-match confidence floor:** `0.70`

At this operating point on the 420 labelled training lines:

| Metric         | Result |
| -------------- | -----: |
| AUTO decisions |     99 |
| AUTO correct   |     97 |
| AUTO wrong     |      2 |
| AUTO precision | 97.98% |
| AUTO coverage  | 23.57% |

Of the 99 `AUTO` decisions:

* 76 were resolved through strong identifier evidence.
* 23 were accepted through lexical/structured matching.

The operating point is intentionally conservative. Reducing the confidence margin increases coverage substantially, but also increases false automatic matches. Since a wrong automatic match is much more costly than sending a line to human review, the higher-margin operating point was retained.

## 2. Reproducible Evaluation

The main evaluation commands are:

```bash
python evaluate_decisions.py
python -m evaluation.noise_analysis
python test_baseline.py
python test_normalizer.py
python test_matcher_variants.py
python benchmark_matcher.py
```

These commands evaluate different parts of the system:

| Script                      | Purpose                                                                          |
| --------------------------- | -------------------------------------------------------------------------------- |
| `evaluate_decisions.py`     | Measures AUTO precision and coverage across confidence and margin thresholds.    |
| `evaluation.noise_analysis` | Measures retrieval and decision behaviour across manually defined noise classes. |
| `test_baseline.py`          | Validates strong barcode and customer-alias resolution.                          |
| `test_normalizer.py`        | Protects normalization behaviour with regression assertions.                     |
| `test_matcher_variants.py`  | Protects specific variant reranking behaviour.                                   |
| `benchmark_matcher.py`      | Measures warm-cache per-line latency.                                            |

### Latency

The matcher latency benchmark measured **4,200 decisions**:

| Metric  |   Latency |
| ------- | --------: |
| Average |  5.936 ms |
| P50     |  6.636 ms |
| P95     |  9.335 ms |
| P99     | 10.625 ms |
| Maximum | 24.864 ms |

The measured P95 latency of **9.335 ms** is comfortably below the required **250 ms per-line budget**.

## 3. Precision Versus Coverage

The following sweep uses the same labelled training set while varying the minimum confidence and confidence-margin requirements.

| Min confidence | Min margin | AUTO | Correct | Wrong | Precision | Coverage |
| -------------: | ---------: | ---: | ------: | ----: | --------: | -------: |
|           0.85 |       0.00 |  268 |     221 |    47 |    82.46% |   63.81% |
|           0.85 |       0.01 |  242 |     221 |    21 |    91.32% |   57.62% |
|           0.85 |       0.03 |  224 |     213 |    11 |    95.09% |   53.33% |
|           0.85 |       0.05 |  211 |     201 |    10 |    95.26% |   50.24% |
|           0.85 |       0.10 |   99 |      97 |     2 |    97.98% |   23.57% |
|           0.90 |       0.00 |  222 |     175 |    47 |    78.83% |   52.86% |
|           0.90 |       0.03 |  182 |     171 |    11 |    93.96% |   43.33% |
|           0.90 |       0.05 |  171 |     161 |    10 |    94.15% |   40.71% |
|           0.90 |       0.10 |   87 |      85 |     2 |    97.70% |   20.71% |
|          0.925 |       0.10 |   76 |      76 |     0 |   100.00% |   18.10% |

The results show why accuracy or coverage alone would be misleading.

For example, removing the margin requirement increases AUTO coverage from **23.57% to 63.81%**, but AUTO precision falls from **97.98% to 82.46%**. The additional coverage therefore comes from automatically accepting more ambiguous candidates.

At the opposite extreme, requiring confidence `>= 0.925` produces **100% AUTO precision**, but reduces the system to only the 76 strongest identifier-based matches.

The selected `0.85 / 0.10` operating point therefore allows some lexical AUTO matching while maintaining a substantially safer precision level.

## 4. Noise-Class Analysis

The training data was segmented into manually defined noise classes based on patterns observed in the order lines.

The purpose of this breakdown is to distinguish failures caused by different input conditions rather than relying on a single aggregate score.

| Noise class          | Rows | Positive GT | Blank GT | Top-1 accuracy | Top-5 recall | AUTO precision | AUTO coverage |
| -------------------- | ---: | ----------: | -------: | -------------: | -----------: | -------------: | ------------: |
| numeric_attributes   |  357 |         266 |       91 |         92.86% |       99.25% |         97.37% |        21.29% |
| measurement_text     |  269 |         203 |       66 |         93.60% |       99.51% |         96.83% |        23.42% |
| has_uom              |  215 |         147 |       68 |         90.48% |       98.64% |         95.56% |        20.93% |
| has_price            |  184 |         167 |       17 |         94.01% |       99.40% |         98.15% |        29.35% |
| conversational_noise |   68 |          57 |       11 |         91.23% |       96.49% |        100.00% |        22.06% |
| has_buyer_sku        |   64 |          64 |        0 |         59.38% |       95.31% |        100.00% |       100.00% |
| short_text           |   51 |          24 |       27 |         41.67% |       95.83% |        100.00% |        47.06% |
| separator_noise      |   48 |          40 |        8 |        100.00% |      100.00% |         85.71% |        29.17% |
| spacing_noise        |   20 |          19 |        1 |         89.47% |       94.74% |        100.00% |        15.00% |
| has_barcode          |   13 |          13 |        0 |         61.54% |      100.00% |        100.00% |        92.31% |
| plain_text           |    7 |           1 |        6 |        100.00% |      100.00% |          0.00% |         0.00% |

Several patterns are important.

First, top-5 recall remains high across most categories even when top-1 accuracy is weaker. This indicates that candidate generation is usually successful and that many remaining failures are ranking or ambiguity problems rather than retrieval failures.

Second, rows containing buyer SKU or barcode identifiers have relatively weak lexical top-1 accuracy but very strong AUTO precision. This is expected because the final matcher evaluates validated identifiers before lexical retrieval.

For example:

* Buyer-SKU rows achieve **100% AUTO precision** and **100% AUTO coverage**.
* Barcode rows achieve **100% AUTO precision** and **92.31% AUTO coverage**.

This supports the identifier-first pipeline design.

Short-text rows also illustrate why raw top-1 accuracy is misleading. Their lexical top-1 accuracy is only **41.67%**, but AUTO precision is **100%**. Many short descriptions do not contain enough attributes to uniquely identify a catalogue item, so the system either relies on stronger identifiers or abstains rather than forcing a lexical prediction.

The separator-noise group has lower AUTO precision at **85.71%**. Manual inspection showed that the two apparent AUTO errors are blank-ground-truth rows with highly plausible exact catalogue matches. These are treated as label or task-ambiguity cases rather than evidence that separator normalization should be weakened.

## 5. Manual error analysis

I manually inspected specific failures rather than treating every disagreement
with the ground truth as the same type of error.

I grouped the cases into four categories:

1. genuine matcher or normalization defects;
2. under-specified text that is correctly recovered by stronger identifiers;
3. intrinsic catalogue/ground-truth ambiguity;
4. likely label problems.

The cost class refers to the likely production consequence:

- **High** — could cause an incorrect automatic SKU selection.
- **Medium** — primarily causes unnecessary human review.
- **Data** — the available input or label does not define a unique software fix.

### 5.1 Genuine matcher defects found and fixed

| line_id | Failure | Root cause | Cost | Fix |
|---|---|---|---|---|
| ACM-T-0071 | `tolsen GRINDING DISC 4.5" flap` initially ranked a Grinding disc above the GT Flap disc | Lexical token-set similarity treated `grinding` and `flap` as ordinary competing tokens and did not recognise the more specific product variant | High | Added explicit variant extraction and used variant agreement as a ranking-only signal |
| ACM-T-0166 | `BOSCO GRINDING DISC 5" FLAP` initially preferred the Grinding variant | Same variant-ranking problem as ACM-T-0071 | High | Covered by the same variant reranking rule and regression test |
| ACM-T-0179 | `Remax Ball Valve " 1PVC` failed to interpret the intended 1-inch dimension correctly | Malformed inch marker appeared before the number rather than after it | High | Added normalization for misplaced inch markers, producing `1in pvc` |
| ACM-T-0249 | Malay colour term `putih` did not match catalogue colour `White` | Missing multilingual normalization for an unambiguous colour synonym | Medium | Added `putih -> white` normalization |

These four failures represented reusable capabilities rather than one-off
ground-truth patches. Regression tests were added for the normalization and
variant-ranking behaviour.

### 5.2 Under-specified lexical text recovered by identifiers

The following cases are lexical top-1 disagreements, but the input text does
not contain enough information to select the exact SKU reliably. A valid
customer SKU alias or barcode resolves the correct item before the lexical lane
is allowed to make the final decision.

| line_id | Input symptom | Missing distinguishing information | Identifier evidence | Cost | Production treatment |
|---|---|---|---|---|---|
| ACM-T-0010 | `Vermont GI Wire Soft` | Wire gauge | buyer SKU alias | Medium | Use alias; otherwise review |
| ACM-T-0011 | `need Kanto Grinder Disc Grinding` | Disc size | buyer SKU alias | Medium | Use alias; otherwise review |
| ACM-T-0035 | `Stallion Hose Clip Zinc` | Diameter/range | buyer SKU alias | Medium | Use alias; otherwise review |
| ACM-T-0037 | `Vermont - Valve` | Size and material | buyer SKU alias | High | Use alias; never invent attributes |
| ACM-T-0091 | `Vermont PVC 32mm Class` | Class letter | barcode | High | Barcode resolves exact SKU |
| ACM-T-0103 | `M6x50 304` | Brand | buyer SKU alias | Medium | Use alias; otherwise review |
| ACM-T-0105 | `GI Wire #18 Hard` | Brand | buyer SKU alias | Medium | Use alias; otherwise review |
| ACM-T-0118 | `Plug 12mm Blue` | Brand | barcode | Medium | Barcode resolves exact SKU |
| ACM-T-0132 | `GI Wire` | Brand, gauge and grade | buyer SKU alias | High | Use alias; lexical AUTO would be unsafe |
| ACM-T-0133 | `urgent Pipe 40mm Class D` | Brand | buyer SKU alias | Medium | Use alias; otherwise review |
| ACM-T-0186 | `PVC 20mm Class E` | Brand | barcode | Medium | Barcode resolves exact SKU |
| ACM-T-0255 | `urgent Self Drilling Screw #10 x` | Brand, length and finish | buyer SKU alias | High | Use alias; otherwise review |

These rows should not be "fixed" by introducing defaults such as a preferred
brand, colour, size, or class. Those rules would make training accuracy look
better while creating unjustified behaviour on unseen data.

### 5.3 Intrinsic ambiguity / insufficient context

| line_id | Failure | Root cause | Cost | Production treatment |
|---|---|---|---|---|
| ACM-T-0209 | `Masking Tape 24mm High Temp` does not identify the labelled Bulk/Tolsen SKU | The source omits both the brand and any Bulk marker; several catalogue items satisfy the visible description | Data | Keep multiple candidates and send to review |
| NRD-T-0009 | `Golden Pantry Full Cream Milk UHT 200ml` has both base and Bulk catalogue twins | Both active items have effectively identical visible evidence, and the barcode is shared/ambiguous | Data | Do not force either twin; review unless stronger context exists |

I tested whether absence of the word `Bulk` could safely imply the base item.
The training data contains examples in both directions, so a blanket
`no Bulk token -> prefer base` rule was rejected.

### 5.4 Likely label / task ambiguity

Two blank-ground-truth rows produced highly plausible exact catalogue matches:

| line_id | Observed behaviour | Why the label is questionable | Production treatment |
|---|---|---|---|
| ACM-T-0177 | Exact textual match to a Vermont Self Drilling Screw variant, but GT is blank | The visible product evidence is strong; the main apparent mismatch is order UOM versus catalogue packet UOM | Treat as label-suspect; do not introduce a hard UOM rejection |
| ACM-T-0212 | Exact textual match to a Stallion Self Drilling Screw variant, but GT is blank | Same pattern: exact product description with an ea/unit versus Packet UOM difference | Treat as label-suspect; require data review rather than matcher weakening |

A hard UOM mismatch rule was considered and rejected because the labelled data
contains positive examples where `ea` or `unit` legitimately maps to an item
whose stock UOM is `Packet`.

### 5.5 Summary of the failure investigation

The investigation changed how I interpreted the raw lexical error count.

After the targeted fixes, there were 32 remaining positive-ground-truth
lexical top-1 disagreements.

Of those:

- 30 were correctly resolved by the identifier lane;
- 0 identifier resolutions were incorrect;
- 0 barcode/alias conflicts occurred;
- only 2 had no unique identifier resolution, and both were intrinsically
  ambiguous or under-specified.

Therefore I stopped adding lexical heuristics at that point. Further tuning
against these cases would mainly teach arbitrary catalogue preferences rather
than improve generalisation.

## 6. Label and task ambiguity

The provided labels are useful for evaluation, but they are not perfect.
I found several rows where the ground truth appears questionable or where the
source text does not contain enough information to justify one unique answer.

This matters because blindly optimising against those labels would encourage
the matcher to learn arbitrary catalogue preferences.

### 6.1 ACM-T-0177 — likely incorrect blank label

The line describes:

`Vermont Self Drilling Screw #10 x 1-1/2" Stainless 410`

The catalogue contains an exact matching item, but the labelled
`gt_item_code` is blank.

The main visible difference is that the order line uses a unit-like UOM while
the catalogue item is stocked as `Packet`.

I considered treating UOM mismatch as a hard rejection rule, but rejected that
idea because the labelled data contains multiple positive examples where
`ea` or `unit` legitimately maps to a catalogue item stocked as `Packet`.

Therefore I treat this row as label-suspect rather than evidence that the
matcher should reject exact product matches whenever the UOM differs.

In production I would send this case to data-quality review and record the
operator-confirmed outcome before changing matching policy.

### 6.2 ACM-T-0212 — same likely label problem

This row has the same pattern:

`Stallion Self Drilling Screw #8 x 3/4" Stainless 410`

The catalogue contains an exact visible product match, while the ground truth
is blank.

Again, the apparent discrepancy is mostly the input UOM versus catalogue
stock UOM.

Because positive labelled rows show that unit-to-packet mappings can be valid,
I do not treat this as a safe software rejection rule.

This strengthens the conclusion that at least some blank ground-truth rows
represent annotation ambiguity rather than true no-match cases.

### 6.3 ACM-T-0209 — under-specified ground truth

The source text is:

`pls send Masking Tape 24mm High Temp`

The labelled item is a specific Bulk/Tolsen variant, but the source text
contains neither the brand nor a Bulk marker.

Several active catalogue items satisfy the visible description.

I tested whether the absence of the word `Bulk` could safely imply the base
item, but the training data contains examples where a Bulk item is the labelled
answer even when the source does not explicitly say `Bulk`.

Therefore there is no evidence for a deterministic rule that uniquely selects
the labelled item.

In production this line should remain in review unless additional context is
available, such as customer-specific history, a buyer SKU, barcode, or a
confirmed previous order.

### 6.4 NRD-T-0009 — ambiguous catalogue twins

The source text is:

`Golden Pantry Full Cream Milk UHT 200ml`

The catalogue contains both a base item and a `(Bulk)` twin with effectively
identical visible matching evidence.

The barcode is also not uniquely useful because it maps ambiguously across the
active twins.

The ground truth chooses the base item, but the supplied line does not contain
evidence that safely distinguishes base from Bulk.

I therefore classify this row as under-specified rather than a matcher defect.

In production I would either:

- require stronger order context;
- use validated customer-specific purchase history;
- expose both candidates to review; or
- fix the catalogue/identifier contract so active twins are distinguishable.

### 6.5 Production treatment of questionable labels

Questionable labels should not be silently overwritten or used as direct
training truth.

I would maintain a small adjudication workflow:

1. flag rows where strong evidence contradicts the label;
2. record the evidence and matcher version;
3. have an operator or catalogue owner confirm the correct outcome;
4. update the labelled evaluation set only after adjudication;
5. keep disputed rows separate from ordinary regression metrics until resolved.

This prevents label noise from turning into matcher rules and then feeding back
into future alias history.

## 7. Regression safety and release gates

The evaluation harness should not only describe matcher quality; it should stop
unsafe changes from being released.

I would treat the current labelled training set as a regression benchmark and
apply explicit release gates to every matcher change.

### 7.1 Hard correctness gates

The following conditions should fail the build immediately:

- any cross-tenant prediction;
- any strong identifier regression where barcode or validated alias resolution
  becomes incorrect;
- any duplicate or invalid output rows in `predictions.csv`;
- any confidence value outside `[0,1]`;
- any regression test failure in normalization or variant handling;
- matcher p95 latency above the required 250 ms per line.

Cross-tenant violations are especially important because tenant isolation is a
hard correctness boundary rather than a ranking preference.

### 7.2 AUTO precision gate

The primary quality gate should be AUTO precision at the selected operating
point.

Current reference:

- minimum confidence: `0.85`
- minimum confidence margin: `0.10`
- AUTO precision: `97.98%`
- AUTO coverage: `23.57%`

A matcher change should not be accepted if it materially reduces AUTO
precision unless the business explicitly approves a new cost trade-off.

A practical CI gate would require:

- AUTO precision >= 97%;
- zero new incorrect strong-identifier resolutions.

Coverage may move in either direction, but an increase in coverage should be
accepted only if precision remains above the safety threshold.

### 7.3 Retrieval regression gate

Candidate generation should also be monitored independently of AUTO decisions.

The current broad retrieval behaviour is strong, with very high top-k recall
across the main noise classes.

A useful regression gate is:

- positive-GT top-5 recall must not materially decrease;
- any GT item that was previously present in the top 20 but disappears should
  be investigated.

This separates retrieval regressions from confidence-calibration regressions.

### 7.4 Targeted regression tests

Specific bugs found during manual error analysis are protected with dedicated
tests.

Current examples include:

- normal inch and fractional-inch normalization;
- `SS304 -> stainless 304`;
- `ZP -> zinc plated`;
- `putih -> white`;
- malformed `" 1PVC -> 1in pvc`;
- Flap variants ranking above generic Grinding variants when the source
  explicitly contains `flap`.

These tests protect reusable behaviours rather than individual ground-truth
rows.

### 7.5 Preventing benchmark rot

A fixed benchmark can become misleading if the production distribution changes.

To reduce that risk I would:

1. version the evaluation dataset and matcher configuration together;
2. keep historical metrics for each release;
3. add newly adjudicated production failures to the regression set;
4. monitor performance by tenant and noise class rather than aggregate only;
5. periodically review whether the benchmark still reflects current order
   formats and catalogue behaviour;
6. keep disputed or label-suspect rows separately tracked until adjudicated.

The benchmark should therefore evolve through reviewed production evidence,
not through silently changing labels to make the current matcher look better.

## 8. Evaluation conclusion

The main result of the evaluation is not a single accuracy number.

The matcher deliberately trades coverage for high-confidence automation:

- strong identifiers provide a high-precision first lane;
- lexical retrieval maintains high candidate recall;
- structured evidence improves ranking;
- confidence and candidate separation decide whether automation is safe;
- ambiguous cases remain in REVIEW rather than being forced to a catalogue
  item.

At the selected operating point the matcher achieves 97.98% AUTO precision at
23.57% AUTO coverage on the labelled set, while maintaining a measured p95
latency of 9.335 ms per line.

Manual error analysis also showed that many apparent lexical failures are
under-specified descriptions that are correctly recovered by identifiers, and
that several remaining disagreements are label or catalogue ambiguities rather
than useful targets for additional heuristics.

For that reason I stopped tuning the matcher once additional rules no longer
had clear evidence that they would generalise beyond the labelled training
set.