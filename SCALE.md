# Task 6 — Scale and Rollout

At 500 tenants, roughly 4 million catalogue rows, and about 150,000 order lines per day, I would not expect raw matcher CPU time to fail first. The larger risks are catalogue/index management, tenant-specific state, alias growth, and safe rollout.

## 1. What Breaks First

The current matcher runs at roughly 10 ms p95 per line, so single-line inference has substantial headroom.

The first pressure points would likely be:

- catalogue loading and preprocessing;
- repeated rebuilding of tenant search structures;
- memory pressure from keeping many catalogues hot;
- alias-table growth and conflict checking;
- large tenants dominating latency;
- REVIEW-queue growth if confidence distributions shift.

I would monitor these per tenant rather than only globally:

- p50/p95/p99 matching latency;
- catalogue size and preprocessing time;
- cache hit rate and memory use;
- AUTO precision and coverage;
- REVIEW rate and queue age;
- alias-conflict rate.

Aggregate metrics can hide one unhealthy tenant.

## 2. Catalogue and Index Scaling

I would not repeatedly scan raw catalogue files or rebuild normalised representations per request.

Tenant isolation would remain a physical retrieval boundary, with reusable tenant-scoped search structures and bounded caching.

A cold tenant should still work correctly, although it may temporarily pay the cost of loading or rebuilding its retrieval structure.

If an embedding lane were later justified, I would keep the same tenant-scoped design.

A tenant changing 40,000 items should not require rebuilding a global vector index. I would use:

- incremental updates where supported;
- versioned tenant indexes;
- atomic switch-over from the previous index;
- the last known-good index while rebuilding;
- catalogue-version metadata attached to predictions.

A stale semantic index may reduce recall, but it must never bypass tenant isolation or the final AUTO-safety policy.

## 3. Preventing Alias Feedback Loops

The alias table is potentially more dangerous than the catalogue because it learns from confirmed orders.

If every operator confirmation immediately becomes trusted evidence, one incorrect confirmation can create a bad alias. That alias can then drive a wrong AUTO decision, which may be confirmed again and strengthen the same mistake.

I would therefore treat confirmation as evidence, not permanent truth.

An alias should retain:

- tenant and customer;
- buyer SKU and mapped item;
- source and confidence;
- creation and last-confirmed time;
- expiry or validity window;
- confirmation history;
- conflicting mappings.

New aliases should start at lower trust.

Promotion to strong identifier status should require repeated evidence, recency, and no active conflict. A conflicting confirmation should reduce trust or send the mapping to review rather than silently replacing the previous mapping.

History should be retained so a bad alias can be rolled back and affected predictions identified.

Because wrong AUTO matches are much more expensive than review, uncertain alias learning should bias toward REVIEW.

## 4. Safe Matcher Rollout

I would use both **shadow** and **canary** rollout.

In shadow mode, the current production matcher continues to act while the new matcher runs in parallel.

I would compare:

- AUTO decision disagreements;
- candidate changes;
- confidence changes;
- cross-tenant safety;
- latency;
- REVIEW-rate changes.

The highest-risk cases are where the new version changes a previous REVIEW or rejection into AUTO.

If shadow results are acceptable, I would canary the new matcher on a small but representative set of tenants covering different catalogue sizes, noise patterns, and maturity levels.

Rollout gates would include:

- zero cross-tenant violations;
- no strong-identifier correctness regression;
- acceptable latency;
- no material AUTO-precision drop;
- bounded REVIEW-volume change.

## 5. Delayed Ground Truth

Production correctness may only become visible days later, after operator review, fulfilment, or customer feedback.

Every prediction should therefore retain:

- matcher version;
- catalogue version;
- confidence and evidence;
- candidate set;
- eventual operator or fulfilment outcome.

This makes delayed evaluation attributable to the exact version that produced the decision.

A rollout should remain reversible until enough delayed outcomes are available. If a canary increases AUTO coverage but later shows more fulfilment errors, it should be rolled back even if short-term metrics looked better.

## 6. Longer-Term Architecture

At this scale I would separate:

1. catalogue ingestion and validation;
2. tenant-scoped retrieval/index building;
3. online matching;
4. review workflow;
5. alias learning;
6. offline evaluation and release gating.

The online matcher should remain relatively simple and deterministic.

More expensive learning, recalibration, label adjudication, and catalogue-quality work should happen offline where they can be measured before affecting fulfilment.

The principle remains the same at scale:

> Uncertainty should reduce automation, not increase confidence.