from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


errors = []


for line in rows:

    gt = line["gt_item_code"].strip()

    # --------------------------------------------------
    # Only positive-GT rows
    # --------------------------------------------------

    if not gt:
        continue


    # --------------------------------------------------
    # Rank a reasonably large candidate set
    # --------------------------------------------------

    candidates = matcher.rank_candidates(
        line,
        limit=20,
        retrieval_limit=50,
    )

    if not candidates:
        errors.append(
            {
                "line": line,
                "gt": gt,
                "gt_rank": None,
                "top": None,
                "candidates": [],
            }
        )
        continue


    top = candidates[0]
    prediction = top["item"]["item_code"]


    # --------------------------------------------------
    # Correct top-1 rows are not errors
    # --------------------------------------------------

    if prediction == gt:
        continue


    # --------------------------------------------------
    # Find GT rank
    # --------------------------------------------------

    gt_rank = None

    for position, candidate in enumerate(
        candidates,
        start=1,
    ):

        if candidate["item"]["item_code"] == gt:
            gt_rank = position
            break


    errors.append(
        {
            "line": line,
            "gt": gt,
            "gt_rank": gt_rank,
            "top": top,
            "candidates": candidates,
        }
    )


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("=== POSITIVE GT TOP-1 ERRORS ===")
print("count:", len(errors))

print()

print(
    "GT at rank 2:",
    sum(
        error["gt_rank"] == 2
        for error in errors
    ),
)

print(
    "GT in top 3:",
    sum(
        error["gt_rank"] is not None
        and error["gt_rank"] <= 3
        for error in errors
    ),
)

print(
    "GT in top 5:",
    sum(
        error["gt_rank"] is not None
        and error["gt_rank"] <= 5
        for error in errors
    ),
)

print(
    "GT in top 20:",
    sum(
        error["gt_rank"] is not None
        and error["gt_rank"] <= 20
        for error in errors
    ),
)

print(
    "GT missing from top 20:",
    sum(
        error["gt_rank"] is None
        for error in errors
    ),
)


# --------------------------------------------------
# Group errors by diagnostic type
# --------------------------------------------------

rank_2_errors = [
    error
    for error in errors
    if error["gt_rank"] == 2
]

top_5_errors = [
    error
    for error in errors
    if (
        error["gt_rank"] is not None
        and 3 <= error["gt_rank"] <= 5
    )
]

deep_errors = [
    error
    for error in errors
    if (
        error["gt_rank"] is not None
        and error["gt_rank"] > 5
    )
]

missing_errors = [
    error
    for error in errors
    if error["gt_rank"] is None
]


def print_error(error):

    line = error["line"]
    gt = error["gt"]
    top = error["top"]
    candidates = error["candidates"]

    print()
    print("=" * 80)

    print("line_id:", line["line_id"])
    print("tenant:", line["tenant"])
    print("customer:", line["customer_id"])

    print()
    print("raw_text:", line["raw_text"])
    print("qty:", line["qty"])
    print("uom:", line["uom_text"])
    print("unit_price:", line["unit_price"])
    print("buyer_sku:", line["buyer_sku"])
    print("barcode:", line["raw_barcode"])
    print("notes:", line["notes"])

    print()
    print("GT:", gt)
    print("GT rank:", error["gt_rank"])

    gt_item = matcher.item_lookup[
        line["tenant"]
    ].get(gt)

    if gt_item:

        print()
        print("--- GROUND TRUTH ITEM ---")

        print(
            "name:",
            gt_item["item_name"],
        )

        print(
            "brand:",
            gt_item["brand"],
        )

        print(
            "stock_uom:",
            gt_item["stock_uom"],
        )

        print(
            "price:",
            gt_item["list_price"],
        )

        print(
            "description:",
            gt_item["description"],
        )


    if top:

        item = top["item"]

        print()
        print("--- TOP PREDICTION ---")

        print(
            "code:",
            item["item_code"],
        )

        print(
            "name:",
            item["item_name"],
        )

        print(
            "confidence:",
            round(
                top["confidence_score"],
                4,
            ),
        )

        print(
            "lexical:",
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
            "stock_uom:",
            item["stock_uom"],
        )

        print(
            "price:",
            item["list_price"],
        )


    print()
    print("--- TOP 5 CANDIDATES ---")

    for position, candidate in enumerate(
        candidates[:5],
        start=1,
    ):

        item = candidate["item"]

        marker = ""

        if item["item_code"] == gt:
            marker = "  <-- GT"

        print()
        print(
            f"#{position}",
            item["item_code"],
            marker,
        )

        print(
            "  name:",
            item["item_name"],
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
            "  rank_score:",
            round(
                candidate["rank_score"],
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
            item["stock_uom"],
        )

        print(
            "  price:",
            item["list_price"],
        )


# --------------------------------------------------
# Most useful group:
# GT retrieved but ranked second
# --------------------------------------------------

print()
print("=== GT AT RANK 2 ===")
print("count:", len(rank_2_errors))

for error in rank_2_errors[:10]:
    print_error(error)


# --------------------------------------------------
# GT ranks 3-5
# --------------------------------------------------

print()
print("=== GT AT RANK 3-5 ===")
print("count:", len(top_5_errors))

for error in top_5_errors[:10]:
    print_error(error)


# --------------------------------------------------
# GT retrieved deeper than top 5
# --------------------------------------------------

print()
print("=== GT BELOW TOP 5 ===")
print("count:", len(deep_errors))

for error in deep_errors[:10]:
    print_error(error)


# --------------------------------------------------
# GT not retrieved at all
# --------------------------------------------------

print()
print("=== GT MISSING FROM TOP 20 ===")
print("count:", len(missing_errors))

for error in missing_errors[:10]:
    print_error(error)