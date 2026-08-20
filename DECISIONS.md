# Decision Log

## D-01 — Optimise for precision before coverage

**Context:** A wrong automatic match is far more expensive than sending an order line to human review.

**Options:**
- maximise overall top-1 accuracy;
- maximise AUTO coverage;
- maximise coverage subject to a high AUTO-precision requirement.

**Chose:** maximise useful AUTO coverage while keeping AUTO precision very high.

**Evidence:** At confidence `0.85` with no margin requirement, AUTO coverage was 63.81% but precision fell to 82.46%. Adding a `0.10` margin reduced coverage to 23.57% while increasing AUTO precision to 97.98%.

A stricter `0.925 / 0.10` operating point achieved 100% measured AUTO precision at 18.10% coverage and slightly better literal cost on the supplied labels. I retained `0.85 / 0.10` because the two additional apparent AUTO errors are both blank-ground-truth rows that manual inspection identified as likely label ambiguities.

**Trade-off:** The selected point automates more lexical matches than the stricter alternative, but accepts two disputed labelled disagreements. More conservative thresholds send more lines to review.

**Reversal trigger:** Revisit the operating point after adjudicating disputed labels, or if the business changes the relative cost of a wrong automatic match versus review.

---

## D-02 — Put strong identifiers before lexical retrieval

**Context:** Some order descriptions omit attributes needed to uniquely identify the correct catalogue item, while buyer SKU aliases or barcodes provide stronger evidence.

**Options:**
- rely primarily on fuzzy text matching;
- combine all signals into one score;
- evaluate validated identifiers before lexical retrieval.

**Chose:** barcode and validated customer aliases are checked before the lexical lane.

**Evidence:** The final evaluation resolved 76 lines using strong identifiers, all 76 correctly. Several lexical top-1 failures were correctly recovered by an identifier.

**Trade-off:** Identifier validation logic becomes part of the critical path.

**Reversal trigger:** Reconsider only if production evidence shows identifier sources are sufficiently unreliable that they should no longer be treated as a stronger lane.

---

## D-03 — Reject unsafe aliases instead of trusting every historical mapping

**Context:** The supplied customer SKU mapping contains expired mappings, conflicting mappings, inferred matches, and varying confidence.

**Options:**
- accept any matching buyer SKU;
- accept only mappings meeting validity and safety checks;
- ignore aliases entirely.

**Chose:** accept only valid, sufficiently trustworthy, unambiguous mappings.

**Evidence:** Inspection of the alias table found conflicting keys and expired mappings. Blindly trusting them could create confident wrong matches.

**Trade-off:** Some lines that have an alias-like value still fall back to lexical matching or review.

**Reversal trigger:** If the upstream alias contract becomes authoritative and guarantees uniqueness, validity, and provenance, simplify the validation lane.

---

## D-04 — Use targeted deterministic normalisation rather than broad guessing

**Context:** Order text contains inconsistent punctuation, inch notation, abbreviations, typos, and some Malay/English mixing.

**Options:**
- leave text mostly untouched;
- add broad heuristic substitutions;
- add narrow reusable normalisation rules supported by observed data.

**Chose:** deterministic normalisation for patterns such as inch notation, fractions, `SS304`, `ZP`, malformed inch markers, and `putih -> white`.

**Evidence:** These changes fixed specific reusable failure patterns and were protected with regression tests.

**Trade-off:** Some unseen language variation will still not be normalised.

**Reversal trigger:** Add new rules only when repeated production evidence shows a general pattern rather than a one-off training example.

---

## D-05 — Treat variant evidence as reranking, not a hard-coded SKU rule

**Context:** Fuzzy similarity sometimes ranked a generic grinding-disc variant above a flap-disc variant even when the source explicitly contained `flap`.

**Options:**
- hard-code the labelled item;
- add a global exact rule for affected SKUs;
- extract variant evidence and use it to rerank candidates.

**Chose:** variant-aware reranking.

**Evidence:** The same failure pattern appeared in multiple rows, including ACM-T-0071 and ACM-T-0166. A reusable variant signal fixed both.

**Trade-off:** The matcher becomes slightly more domain-aware.

**Reversal trigger:** Replace with a broader learned attribute model if the number of product-specific variant rules grows enough to become difficult to maintain.

---

## D-06 — Stop adding lexical heuristics once remaining errors became ambiguous

**Context:** After targeted fixes, most remaining lexical top-1 disagreements were either resolved by identifiers or lacked enough visible information to justify one unique SKU.

**Options:**
- continue adding heuristics until training accuracy increases further;
- introduce arbitrary preferences such as default brand or non-Bulk preference;
- stop tuning when additional rules no longer have evidence they will generalise.

**Chose:** stop adding lexical heuristics.

**Evidence:** Of 32 remaining positive-GT lexical top-1 disagreements, 30 were correctly recovered by the identifier lane. The remaining two were intrinsically ambiguous or under-specified.

**Trade-off:** Raw lexical top-1 accuracy remains below what could be achieved by overfitting the training set.

**Reversal trigger:** Revisit when new labelled production failures reveal a repeated capability gap rather than an ambiguous catalogue choice.

---

## D-07 — Do not add an embedding or LLM inference lane without measured benefit

**Context:** The role involves AI/LLM work, but the assessment requires an offline deterministic matcher and asks semantic techniques to justify their marginal value.

**Options:**
- add embeddings because they are available;
- use an LLM to parse or choose SKUs;
- keep the final path deterministic unless semantic models demonstrate measurable benefit.

**Chose:** no LLM or embedding model in the final matcher.

**Evidence:** The deterministic pipeline already achieved 98.98% top-5 recall and 97.98% AUTO precision at the selected operating point with p95 latency around 10 ms. Many residual failures were missing-information or catalogue-ambiguity problems that semantic similarity cannot resolve.

**Trade-off:** The system may miss semantically similar descriptions that share few lexical signals.

**Reversal trigger:** Test a local semantic lane if production retrieval recall becomes a measurable bottleneck, especially on longer paraphrased descriptions.

---

## D-08 — Rewrite the Task 4 report set-wise instead of micro-optimising correlated subqueries

**Context:** The original report repeatedly executed correlated scans over the match-event ledger and was far too slow over the full reporting window.

**Options:**
- add indexes around the existing correlated structure;
- optimise each expensive metric independently;
- replace repeated correlated work with set-based aggregation.

**Chose:** set-based rewrite first.

**Evidence:** Ablation showed `repeat_items_prev_day` was particularly expensive, but multiple metrics repeated similar work. The first set-based rewrite reduced the supplied ~3,050-second baseline to 16.088 seconds while preserving all 13 baseline columns.

**Trade-off:** The rewritten SQL is structurally different from the starter query and requires careful equivalence validation.

**Reversal trigger:** If a future database engine or schema makes the original correlated form competitive and simpler, re-evaluate.

---

## D-09 — Add one targeted report index rather than many speculative indexes

**Context:** The correct set-based Task 4 rewrite still exceeded the 10-second budget at 16.088 seconds.

**Options:**
- add several indexes on potentially useful columns;
- materialise the report;
- add one index aligned with the tenant/day/latency access pattern used by the p95 calculation.

**Chose:** add one expression index on tenant, report day, and latency.

**Evidence:** After the index, repeated full-window checks passed the 10-second median budget while still matching all 8,666 reference rows on all 13 original columns.

**Trade-off:** Additional index storage and write amplification on a write-heavy event ledger.

**Reversal trigger:** Reconsider the reporting architecture when data volume, report concurrency, or write pressure makes the index trade-off unacceptable.

---

## D-10 — Prefer crash-safe reconciliation over blind retry in ERP sync

**Context:** The vendor ERP can return a timeout after committing a write, uses a limited idempotency window, has second-resolution cursors, and can contain newer edits than the local copy.

**Options:**
- retry failed writes blindly;
- overwrite using the local payload after version conflicts;
- use stable mutation identity and reconcile remote state before deciding whether to retry or accept a prior commit.

**Chose:** stable per-local-mutation idempotency, remote read-back, exact-payload reconciliation, and preservation of divergent conflicts.

**Evidence:** Isolated tests reproduced duplicate writes after 504s, stale overwrites after conflicts, crash recovery after the idempotency window, and new-record collisions. All nine regression tests now pass.

**Trade-off:** The sync logic is more stateful and may leave some records dirty for later review instead of forcing convergence immediately.

**Reversal trigger:** Simplify if the ERP vendor provides durable idempotency keys, transactional batch semantics, explicit timezone timestamps, and a stable pagination cursor.