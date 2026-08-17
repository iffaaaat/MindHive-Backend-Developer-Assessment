from collections import Counter, defaultdict

from src.data_loader import (
    load_training_lines,
    load_uom_reference,
)
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()
uom_reference = load_uom_reference()


# --------------------------------------------------
# Basic order-line UOM distribution
# --------------------------------------------------

print("=== ORDER UOM DISTRIBUTION ===")

uom_counts = Counter(
    row["uom_text"].strip().lower()
    for row in rows
    if row["uom_text"].strip()
)

for uom, count in uom_counts.most_common():
    print(f"{uom!r}: {count}")


# --------------------------------------------------
# Catalogue/reference UOM distribution
# --------------------------------------------------

print("\n=== REFERENCE UOM DISTRIBUTION ===")

reference_counts = Counter(
    row["uom"].strip().lower()
    for row in uom_reference
    if row["uom"].strip()
)

for uom, count in reference_counts.most_common():
    print(f"{uom!r}: {count}")


# --------------------------------------------------
# Compare labelled positive lines against their
# ground-truth item's allowed UOMs
# --------------------------------------------------

allowed_uoms = defaultdict(set)

for row in uom_reference:
    key = (
        row["tenant"],
        row["item_code"],
    )

    allowed_uoms[key].add(
        row["uom"].strip().lower()
    )


print("\n=== POSITIVE LINES WITH UOM ===")

positive_with_uom = 0

examples = []


for line in rows:

    gt = line["gt_item_code"].strip()
    order_uom = line["uom_text"].strip().lower()

    if not gt or not order_uom:
        continue

    positive_with_uom += 1

    gt_uoms = allowed_uoms.get(
        (
            line["tenant"],
            gt,
        ),
        set(),
    )

    examples.append(
        (
            line["line_id"],
            order_uom,
            gt,
            sorted(gt_uoms),
            line["raw_text"],
        )
    )


print(
    "positive rows with UOM:",
    positive_with_uom,
)


# --------------------------------------------------
# Show order UOM -> catalogue UOM relationships
# --------------------------------------------------

relationships = defaultdict(Counter)

for (
    line_id,
    order_uom,
    gt,
    gt_uoms,
    raw_text,
) in examples:

    for catalogue_uom in gt_uoms:
        relationships[order_uom][
            catalogue_uom
        ] += 1


print("\n=== ORDER UOM -> VALID GT UOMS ===")

for order_uom in sorted(relationships):

    print()
    print("ORDER UOM:", repr(order_uom))

    for target_uom, count in (
        relationships[order_uom].most_common()
    ):
        print(
            "   ",
            repr(target_uom),
            "->",
            count,
        )


# --------------------------------------------------
# Blank-GT lines with very strong lexical match
# --------------------------------------------------

print(
    "\n=== BLANK-GT HIGH-CONFIDENCE TEXT MATCHES ==="
)

for line in rows:

    if line["gt_item_code"].strip():
        continue

    candidates = matcher.rank_candidates(
        line,
        limit=5,
        retrieval_limit=20,
    )

    if len(candidates) < 2:
        continue

    top = candidates[0]

    margin = (
        candidates[0]["score"]
        - candidates[1]["score"]
    )

    if (
        top["score"] >= 0.95
        and margin >= 0.08
    ):

        item = top["item"]

        valid_uoms = allowed_uoms.get(
            (
                line["tenant"],
                item["item_code"],
            ),
            set(),
        )

        print()
        print("line:", line["line_id"])
        print("text:", line["raw_text"])
        print(
            "order_uom:",
            repr(
                line["uom_text"].strip().lower()
            ),
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
            "candidate_uoms:",
            sorted(valid_uoms),
        )
        print(
            "score:",
            round(
                top["score"],
                4,
            ),
        )
        print(
            "margin:",
            round(
                margin,
                4,
            ),
        )