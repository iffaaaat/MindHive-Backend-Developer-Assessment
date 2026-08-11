#!/usr/bin/env python3
"""GRADERS ONLY - scores a candidate's predictions.csv against the holdout key.

Stdlib only.

    python3 score_predictions.py \
        --pred candidate/predictions.csv \
        --labels ../data/holdout_labels.GRADERS-ONLY.csv \
        --lines ../data/order_lines_holdout.csv \
        --catalogue ../data/catalogue_acme.csv \
        --catalogue ../data/catalogue_nordic.csv

Cost model (see brief S1), in seconds of operator time:
    correct auto-match   -20   (saved)
    abstention           +40
    wrong auto-match     +800  (20x an abstention)
"""

from __future__ import annotations

import argparse
import csv
import collections

COST_CORRECT = -20.0
COST_ABSTAIN = 40.0
COST_WRONG = 800.0

REQUIRED = ["line_id", "item_code", "confidence", "decision", "reason_code", "candidates"]


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--catalogue", action="append", default=[])
    args = ap.parse_args()

    preds = load(args.pred)
    labels = {r["line_id"]: r for r in load(args.labels)}
    lines = {r["line_id"]: r for r in load(args.lines)}

    # tenant ownership of every item_code, for cross-tenant checks
    owner, disabled = {}, set()
    for path in args.catalogue:
        tenant = "acme" if "acme" in path else "nordic"
        for r in load(path):
            owner[r["item_code"]] = tenant
            if r.get("disabled") == "1":
                disabled.add(r["item_code"])

    print("=" * 66)
    schema_errors = []
    if preds:
        missing_cols = [c for c in REQUIRED if c not in preds[0]]
        if missing_cols:
            schema_errors.append(f"missing columns: {missing_cols}")
    missing_rows = set(labels) - {p["line_id"] for p in preds}
    extra_rows = {p["line_id"] for p in preds} - set(labels)
    if missing_rows:
        schema_errors.append(f"{len(missing_rows)} holdout lines not predicted")
    if extra_rows:
        schema_errors.append(f"{len(extra_rows)} unknown line_ids in predictions")
    if schema_errors:
        print("SCHEMA ERRORS (hard gate):")
        for e in schema_errors:
            print("  -", e)
    else:
        print("schema OK")

    auto = correct = wrong = abstained = 0
    abstain_should = abstain_did_right = 0
    recall3_hits = recall3_total = 0
    cross_tenant = []
    disabled_hits = []
    cost = 0.0
    by_class = collections.defaultdict(lambda: [0, 0, 0])   # cls -> [n, auto, auto_correct]
    by_tenant = collections.defaultdict(lambda: [0, 0, 0])

    for p in preds:
        lid = p["line_id"]
        lab = labels.get(lid)
        if not lab:
            continue
        gt = lab["gt_item_code"].strip()
        cls = lab["gt_class"]
        tenant = lines.get(lid, {}).get("tenant", "?")
        code = (p.get("item_code") or "").strip()
        decision = (p.get("decision") or "").strip().lower()
        is_auto = decision == "auto" and code

        if code and owner.get(code) and owner[code] != tenant:
            cross_tenant.append((lid, tenant, code))
        if is_auto and code in disabled:
            disabled_hits.append((lid, code))

        by_class[cls][0] += 1
        by_tenant[tenant][0] += 1

        if is_auto:
            auto += 1
            by_class[cls][1] += 1
            by_tenant[tenant][1] += 1
            if code == gt:
                correct += 1
                by_class[cls][2] += 1
                by_tenant[tenant][2] += 1
                cost += COST_CORRECT
            else:
                wrong += 1
                cost += COST_WRONG
        else:
            abstained += 1
            cost += COST_ABSTAIN
            if gt:
                recall3_total += 1
                cands = [c.split(":")[0] for c in (p.get("candidates") or "").split("|") if c]
                if gt in cands[:3]:
                    recall3_hits += 1

        if not gt:
            abstain_should += 1
            if not is_auto:
                abstain_did_right += 1

    n = len(labels)
    prec = correct / auto if auto else 0.0
    cov = auto / n if n else 0.0
    # reference points: always-abstain, and a perfect oracle
    cost_abstain_all = COST_ABSTAIN * n
    cost_oracle = sum(COST_CORRECT if labels[l]["gt_item_code"] else COST_ABSTAIN for l in labels)

    print("-" * 66)
    print(f"lines scored          {n}")
    print(f"precision@auto        {prec:.4f}   ({correct} correct / {auto} auto)")
    print(f"coverage              {cov:.4f}")
    print(f"wrong auto-matches    {wrong}")
    print(f"abstentions           {abstained}")
    print(f"abstain correctness   {abstain_did_right}/{abstain_should} "
          f"({(abstain_did_right / abstain_should if abstain_should else 0):.3f}) "
          f"of lines with no correct answer")
    print(f"recall@3 when abstain {recall3_hits}/{recall3_total} "
          f"({(recall3_hits / recall3_total if recall3_total else 0):.3f})")
    print("-" * 66)
    print(f"net cost (op-seconds) {cost:>10.0f}   lower is better")
    print(f"  vs abstain-on-all   {cost_abstain_all:>10.0f}")
    print(f"  vs perfect oracle   {cost_oracle:>10.0f}")
    beat = "YES" if cost < cost_abstain_all else "NO  <-- worse than not shipping it"
    print(f"  beats doing nothing {beat}")
    print("-" * 66)
    print("HARD GATES")
    print(f"  cross-tenant violations: {len(cross_tenant)}"
          + (f"  e.g. {cross_tenant[:3]}" if cross_tenant else ""))
    print(f"  disabled/superseded codes auto-matched: {len(disabled_hits)}"
          + (f"  e.g. {disabled_hits[:3]}" if disabled_hits else ""))
    print("-" * 66)
    print(f"{'class':<16}{'n':>5}{'auto':>7}{'prec':>8}")
    for cls, (tot, a, c) in sorted(by_class.items()):
        print(f"{cls:<16}{tot:>5}{a:>7}{(c / a if a else 0):>8.3f}")
    print("-" * 66)
    print(f"{'tenant':<16}{'n':>5}{'auto':>7}{'prec':>8}")
    for t, (tot, a, c) in sorted(by_tenant.items()):
        print(f"{t:<16}{tot:>5}{a:>7}{(c / a if a else 0):>8.3f}")
    print("=" * 66)


if __name__ == "__main__":
    main()
