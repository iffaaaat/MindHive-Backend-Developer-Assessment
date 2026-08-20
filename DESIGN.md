# Task 1 — Problem Framing and Design

## 1. Objective

The goal is not to maximise raw matching accuracy. The system should automate a match only when the expected value of doing so is better than sending the order line to review.

From the assessment cost model:

- a correct automatic match saves about 20 seconds;
- an abstention costs about 40 seconds of operator time;
- a wrong automatic match costs roughly 20 times an abstention.

A simple utility model is:

```text
utility =
    20 * correct_auto
  - 40 * abstentions
  - 800 * wrong_auto
```

Subject to hard constraints:

```text
cross_tenant_matches = 0
p95_latency <= 250 ms per line
```

In practice, I therefore optimise useful AUTO coverage subject to very high AUTO precision.

The selected operating point on the training set is:

| Parameter | Value |
|---|---:|
| Minimum confidence | 0.85 |
| Minimum candidate margin | 0.10 |
| NO_MATCH floor | 0.70 |
| AUTO precision | 97.98% |
| AUTO coverage | 23.57% |

A stricter `0.925 / 0.10` point produced 100% measured AUTO precision at 18.10% coverage and slightly better literal cost on the supplied labels. I retained `0.85 / 0.10` because the two additional apparent AUTO errors are blank-ground-truth rows that manual inspection identified as likely label ambiguities.

In production, I would have those cases adjudicated and let the business owner responsible for fulfilment cost choose the final precision/coverage point.

## 2. Pipeline

The matcher is ordered from strongest and cheapest evidence to weaker evidence:

```text
Order line
    ↓
Tenant boundary
    ↓
Normalisation
    ↓
Valid barcode / buyer SKU?
    ├─ yes → exact identifier resolution
    └─ no
         ↓
Lexical candidate retrieval
         ↓
Structured / variant-aware reranking
         ↓
Confidence + candidate-margin policy
         ↓
AUTO / REVIEW / NO_MATCH
```

### 2.1 Tenant Isolation

The catalogue and identifier lookup are tenant-scoped before ranking. An ACME order can never resolve to a Nordic item, even if its text or identifier looks similar.

Cross-tenant matching is a hard correctness failure, not a scoring preference.

### 2.2 Normalisation

Text is normalised deterministically before lexical comparison.

The normaliser handles reusable patterns found in the supplied data, including:

- case and punctuation differences;
- inch and fractional dimensions;
- malformed inch placement;
- `SS304 -> stainless 304`;
- `ZP -> zinc plated`;
- narrow multilingual mappings such as `putih -> white`.

I avoided rules that invent missing attributes such as brand, size, colour, or pack type.

### 2.3 Strong Identifier Lanes

Validated barcodes and customer-specific buyer SKU aliases are checked before fuzzy text matching.

Identifier evidence is accepted only when it resolves safely within the tenant and is not ambiguous or invalid.

This ordering matters because several descriptions are too under-specified to identify the exact SKU from text alone, while a valid identifier resolves them unambiguously.

On the current labelled evaluation, **76 lines are resolved through strong identifiers with 100% precision**.

### 2.4 Cold-Start Behaviour

A new tenant does not require alias history to work.

With only its catalogue, the matcher can still perform:

1. tenant-scoped catalogue filtering;
2. normalisation;
3. barcode resolution where available;
4. lexical candidate retrieval;
5. structured reranking;
6. AUTO / REVIEW / NO_MATCH arbitration.

A mature tenant gains additional high-precision evidence from validated customer-specific aliases.

Maturity therefore improves automation coverage; it is not required for the basic correctness path.

### 2.5 Lexical Retrieval and Reranking

If no safe identifier resolves the line, the matcher retrieves candidates using normalised product-name similarity.

Candidate generation is optimised for recall rather than immediate acceptance. On the labelled set, the correct item is in the top five for **292 of 295 positive-ground-truth lines**.

Structured evidence is then used only where the data shows a reusable distinction.

For example, explicit `flap` evidence helps rank a flap-disc variant above a generic grinding-disc variant. This affects ranking rather than hard-coding a particular ground-truth SKU.

### 2.6 Decision Policy

The final stage considers both:

- confidence in the best candidate;
- separation between the best and second-best candidates.

The output is:

- `AUTO` — evidence is strong enough to act automatically;
- `REVIEW` — a plausible candidate exists, but the evidence is not safe enough;
- `NO_MATCH` — candidate evidence is too weak.

This makes "I don't know" part of the architecture rather than an error path.

## 3. LLMs and Embeddings

I did not use an LLM or embedding model in the final inference path.

I first tested cheaper, deterministic mechanisms:

- validated identifiers;
- domain-specific normalisation;
- lexical retrieval;
- structured reranking;
- confidence and margin-based abstention.

These already produced:

- **89.15% positive-GT top-1 accuracy**;
- **98.98% positive-GT top-5 recall**;
- **97.98% AUTO precision** at the selected operating point;
- **p95 matcher latency around 10 ms** on the assessment machine.

The remaining difficult cases are often missing-information or catalogue-ambiguity problems, including:

- omitted attributes;
- conflicting identifiers;
- active catalogue twins;
- questionable labels;
- records that are indistinguishable from the visible order text.

Semantic similarity cannot recover information that is not present.

I would reconsider a local embedding lane if production data showed a repeated class of long or paraphrased descriptions where lexical retrieval failed to place the correct item in the candidate set.

I would keep it only if offline evaluation showed meaningful recall or net-value improvement without reducing AUTO precision.

An LLM could also earn its place before retrieval for extracting structured attributes from long emails, OCR output, or voice transcripts. It should not be allowed to invent an `item_code`.

If the model were unavailable or uncertain, the deterministic matcher should still function and abstain safely.

## 4. Six Expensive Failure Modes

### 4.1 Cross-Tenant Resolution

**Failure:** An order resolves to another tenant's SKU.

**Protection:** Tenant-scoped catalogue and identifier lookup. Any cross-tenant result fails regression checks.

### 4.2 Unsafe Customer Alias

**Failure:** An expired, conflicting, low-confidence, or otherwise invalid alias is treated as truth.

**Protection:** Validate aliases before using them as strong evidence. Ambiguous mappings fall back to weaker matching or review.

### 4.3 Ambiguous Catalogue Twins

**Failure:** Two active catalogue rows have effectively identical visible evidence and the matcher arbitrarily selects one.

**Protection:** Require candidate separation; otherwise abstain.

### 4.4 Under-Specified Order Text

**Failure:** The source omits a distinguishing attribute and the matcher invents it.

**Protection:** Prefer identifiers when available. Otherwise, low separation leads to `REVIEW`. Normalisation never invents absent attributes.

### 4.5 Superseded or Non-Item Records

**Failure:** Strong text similarity selects a disabled or superseded SKU, or an operational row such as a delivery fee.

**Protection:** Catalogue eligibility is handled before automatic resolution.

### 4.6 Overconfident Fuzzy Matching

**Failure:** The top candidate has a high score but is only slightly better than another plausible SKU.

**Protection:** `AUTO` requires both sufficient confidence and sufficient margin.

## 5. Three-Day Boundary

I focused on:

- tenant isolation;
- validated identifiers;
- deterministic normalisation;
- lexical retrieval;
- limited structured reranking;
- explicit abstention;
- confidence calibration;
- latency measurement;
- error analysis;
- regression safety.

I deliberately left out:

### Dense Semantic Retrieval

Current top-k recall is already high, so I do not yet have evidence that embeddings are the next bottleneck.

### Learned Confidence Calibration

The current policy is calibrated empirically. I would revisit learned calibration with more adjudicated production data.

### Automatic Trust of Every Confirmed Order

Immediately promoting every confirmation to strong alias evidence risks feedback loops. A production implementation would require provenance, conflict handling, expiry, and delayed promotion.

### Full Catalogue Deduplication

Ambiguous catalogue twins are partly a data-contract problem, so I abstain rather than redesign the customer's catalogue.

### Broad Generative or Multilingual Parsing

I would add broader language-model support only if production evidence showed a repeated capability gap.

## Conclusion

The highest-value behaviour is not finding a plausible SKU; it is knowing when the evidence is strong enough to act without a human.

The design therefore prioritises tenant isolation and validated identifiers, uses lexical retrieval to generate candidates cheaply, applies structured evidence only where it generalises, and reserves automatic decisions for candidates with both high confidence and clear separation.

Semantic models, richer calibration, and learned customer history can be added later, but only after measured evidence shows that they improve the system's expected value.