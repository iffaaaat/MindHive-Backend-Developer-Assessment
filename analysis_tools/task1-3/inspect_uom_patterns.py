from collections import Counter

from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


positive_gt_pairs = Counter()
blank_gt_top_pairs = Counter()

positive_examples = []
blank_examples = []


for line in rows:

    gt = line["gt_item_code"].strip()
    input_uom = str(line["uom_text"]).strip().lower()

    # --------------------------------------------------
    # Positive-GT rows
    # --------------------------------------------------

    if gt:

        # Find the actual GT item among ranked candidates.
        # Use a large retrieval window for analysis.
        candidates = matcher.rank_candidates(
            line,
            limit=100,
            retrieval_limit=100,
        )

        gt_candidate = None

        for candidate in candidates:

            item = candidate["item"]

            if item["item_code"] == gt:
                gt_candidate = candidate
                break

        if gt_candidate is None:
            continue

        item = gt_candidate["item"]

        stock_uom = str(
            item["stock_uom"]
        ).strip().lower()

        pair = (
            input_uom,
            stock_uom,
        )

        positive_gt_pairs[pair] += 1

        if (
            input_uom in {"ea", "unit"}
            and stock_uom == "packet"
        ):
            positive_examples.append(
                {
                    "line": line,
                    "item": item,
                }
            )

    # --------------------------------------------------
    # Blank-GT rows
    # --------------------------------------------------

    else:

        candidates = matcher.rank_candidates(
            line,
            limit=20,
            retrieval_limit=30,
        )

        if not candidates:
            continue

        top = candidates[0]

        top_score = top["confidence_score"]

        if len(candidates) >= 2:

            competitor_score = max(
                candidate["confidence_score"]
                for candidate in candidates[1:]
            )

            margin = (
                top_score
                - competitor_score
            )

        else:
            margin = top_score

        # Only examine strong blank-GT candidates.
        if (
            top_score >= 0.85
            and margin >= 0.10
        ):

            item = top["item"]

            stock_uom = str(
                item["stock_uom"]
            ).strip().lower()

            pair = (
                input_uom,
                stock_uom,
            )

            blank_gt_top_pairs[pair] += 1

            blank_examples.append(
                {
                    "line": line,
                    "item": item,
                    "score": top_score,
                    "margin": margin,
                }
            )


# --------------------------------------------------
# Positive GT UOM patterns
# --------------------------------------------------

print("=== POSITIVE GT UOM PAIRS ===")

for pair, count in positive_gt_pairs.most_common():

    input_uom, stock_uom = pair

    print(
        f"{input_uom or '<blank>'}"
        f" -> "
        f"{stock_uom or '<blank>'}: "
        f"{count}"
    )


# --------------------------------------------------
# Critical check
# --------------------------------------------------

print()
print("=== POSITIVE GT: EA/UNIT -> PACKET ===")

print(
    "count:",
    len(positive_examples),
)

for example in positive_examples[:20]:

    line = example["line"]
    item = example["item"]

    print()
    print("=" * 80)

    print(
        "line_id:",
        line["line_id"],
    )

    print(
        "text:",
        line["raw_text"],
    )

    print(
        "input_uom:",
        line["uom_text"],
    )

    print(
        "GT:",
        line["gt_item_code"],
    )

    print(
        "GT item:",
        item["item_code"],
    )

    print(
        "GT name:",
        item["item_name"],
    )

    print(
        "stock_uom:",
        item["stock_uom"],
    )


# --------------------------------------------------
# Strong blank GT UOM patterns
# --------------------------------------------------

print()
print("=== STRONG BLANK GT UOM PAIRS ===")

for pair, count in blank_gt_top_pairs.most_common():

    input_uom, stock_uom = pair

    print(
        f"{input_uom or '<blank>'}"
        f" -> "
        f"{stock_uom or '<blank>'}: "
        f"{count}"
    )


print()
print("=== STRONG BLANK GT EXAMPLES ===")

for example in blank_examples:

    line = example["line"]
    item = example["item"]

    print()
    print("=" * 80)

    print(
        "line_id:",
        line["line_id"],
    )

    print(
        "text:",
        line["raw_text"],
    )

    print(
        "input_uom:",
        line["uom_text"],
    )

    print(
        "candidate:",
        item["item_code"],
    )

    print(
        "candidate_name:",
        item["item_name"],
    )

    print(
        "stock_uom:",
        item["stock_uom"],
    )

    print(
        "score:",
        round(
            example["score"],
            4,
        ),
    )

    print(
        "margin:",
        round(
            example["margin"],
            4,
        ),
    )