from collections import Counter

from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


blank_rows = []


for line in rows:

    gt = line["gt_item_code"].strip()

    if gt:
        continue

    candidates = matcher.rank_candidates(
        line,
        limit=20,
        retrieval_limit=30,
    )

    if not candidates:
        blank_rows.append(
            {
                "line": line,
                "top": None,
                "top_score": 0.0,
                "margin": 0.0,
                "candidates": [],
            }
        )
        continue

    chosen = candidates[0]

    top_score = (
        chosen["confidence_score"]
    )

    if len(candidates) >= 2:

        strongest_competitor_confidence = max(
            candidate["confidence_score"]
            for candidate in candidates[1:]
        )

        margin = (
            chosen["confidence_score"]
            - strongest_competitor_confidence
        )

    else:
        margin = top_score


    blank_rows.append(
        {
            "line": line,
            "top": chosen,
            "top_score": top_score,
            "margin": margin,
            "candidates": candidates,
        }
    )


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("=== BLANK GT SUMMARY ===")
print("total blank GT:", len(blank_rows))

print()

print(
    "top_score >= 0.95:",
    sum(
        row["top_score"] >= 0.95
        for row in blank_rows
    ),
)

print(
    "top_score >= 0.90:",
    sum(
        row["top_score"] >= 0.90
        for row in blank_rows
    ),
)

print(
    "top_score >= 0.85:",
    sum(
        row["top_score"] >= 0.85
        for row in blank_rows
    ),
)

print(
    "top_score < 0.85:",
    sum(
        row["top_score"] < 0.85
        for row in blank_rows
    ),
)

print()

print(
    "margin >= 0.10:",
    sum(
        row["margin"] >= 0.10
        for row in blank_rows
    ),
)

print(
    "margin >= 0.05:",
    sum(
        row["margin"] >= 0.05
        for row in blank_rows
    ),
)

print(
    "margin >= 0.03:",
    sum(
        row["margin"] >= 0.03
        for row in blank_rows
    ),
)

print(
    "margin < 0.03:",
    sum(
        row["margin"] < 0.03
        for row in blank_rows
    ),
)


# --------------------------------------------------
# Combined bands
# --------------------------------------------------

print()
print("=== SCORE + MARGIN BANDS ===")

bands = [
    (0.95, 0.10),
    (0.90, 0.10),
    (0.85, 0.10),
    (0.85, 0.05),
    (0.85, 0.03),
]

for score_threshold, margin_threshold in bands:

    count = sum(
        (
            row["top_score"] >= score_threshold
            and row["margin"] >= margin_threshold
        )
        for row in blank_rows
    )

    print(
        f"score>={score_threshold:.2f}, "
        f"margin>={margin_threshold:.2f}:",
        count,
    )


# --------------------------------------------------
# High-confidence blank GT rows
# --------------------------------------------------

print()
print("=== HIGH-CONFIDENCE BLANK GT ===")

high_confidence = [
    row
    for row in blank_rows
    if (
        row["top_score"] >= 0.85
        and row["margin"] >= 0.10
    )
]

print(
    "count:",
    len(high_confidence),
)


for row in high_confidence:

    line = row["line"]
    top = row["top"]
    candidates = row["candidates"]

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
        "buyer_sku:",
        line["buyer_sku"],
    )

    print(
        "barcode:",
        line["raw_barcode"],
    )

    print(
        "input_uom:",
        line["uom_text"],
    )

    print(
        "unit_price:",
        line["unit_price"],
    )

    print(
        "GT:",
        "<BLANK>",
    )

    if top:

        item = top["item"]

        print()
        print("--- TOP MATCH ---")

        print(
            "candidate:",
            item["item_code"],
        )

        print(
            "candidate_name:",
            item["item_name"],
        )

        print(
            "confidence_score:",
            round(
                row["top_score"],
                4,
            ),
        )

        print(
            "margin:",
            round(
                row["margin"],
                4,
            ),
        )

        print(
            "lexical_score:",
            round(
                top["lexical_score"],
                4,
            ),
        )

        print(
            "brand_match:",
            top["brand_match"],
        )

        print(
            "numeric_score:",
            round(
                top["numeric_score"],
                4,
            ),
        )

        print(
            "rank_score:",
            round(
                top["rank_score"],
                4,
            ),
        )

        print(
            "price_score:",
            round(
                top["price_score"],
                4,
            ),
        )

        print(
            "candidate_uom:",
            item["stock_uom"],
        )

        print(
            "list_price:",
            item["list_price"],
        )

        print(
            "description:",
            item["description"],
        )

        print()
        print("--- TOP 5 CANDIDATES ---")

        for position, candidate in enumerate(
            candidates[:5],
            start=1,
        ):

            candidate_item = candidate["item"]

            print()
            print(
                f"#{position}",
                candidate_item["item_code"],
            )

            print(
                "  name:",
                candidate_item["item_name"],
            )

            print(
                "  confidence:",
                round(
                    candidate["confidence_score"],
                    4,
                ),
            )

            print(
                "  lexical:",
                round(
                    candidate["lexical_score"],
                    4,
                ),
            )

            print(
                "  brand_match:",
                candidate["brand_match"],
            )

            print(
                "  numeric_score:",
                round(
                    candidate["numeric_score"],
                    4,
                ),
            )

            print(
                "  price_score:",
                round(
                    candidate["price_score"],
                    4,
                ),
            )

            print(
                "  stock_uom:",
                candidate_item["stock_uom"],
            )

            print(
                "  list_price:",
                candidate_item["list_price"],
            )


# --------------------------------------------------
# Lowest-confidence examples
# --------------------------------------------------

print()
print("=== LOW-CONFIDENCE BLANK GT EXAMPLES ===")

low_confidence = sorted(
    blank_rows,
    key=lambda row: (
        row["top_score"],
        row["margin"],
    ),
)


for row in low_confidence[:20]:

    line = row["line"]

    print()

    print(
        line["line_id"],
        "| score=",
        round(row["top_score"], 4),
        "| margin=",
        round(row["margin"], 4),
        "|",
        line["raw_text"],
    )