from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


SCORE_THRESHOLD = 0.85
MARGIN_THRESHOLD = 0.10


wrong_auto = []


for line in rows:

    gt = line["gt_item_code"].strip()

    barcode_match = matcher.resolve_barcode(line)
    alias_match = matcher.resolve_alias(line)

    prediction = None
    source = None

    # --------------------------------------------------
    # Strong identifier lane
    # --------------------------------------------------

    if barcode_match and alias_match:

        if (
            barcode_match["item_code"]
            == alias_match["item_code"]
        ):
            prediction = barcode_match["item_code"]
            source = "barcode+alias"

    elif barcode_match:

        prediction = barcode_match["item_code"]
        source = "barcode"

    elif alias_match:

        prediction = alias_match["item_code"]
        source = "alias"


    # --------------------------------------------------
    # Lexical lane
    # --------------------------------------------------

    candidates = matcher.rank_candidates(
        line,
        limit=20,
        retrieval_limit=20,
    )

    top_score = 0.0
    margin = 0.0

    if prediction is None and candidates:

        top_score = (
            candidates[0]["confidence_score"]
        )

        if len(candidates) >= 2:

            strongest_competitor_confidence = max(
                candidate["confidence_score"]
                for candidate in candidates[1:]
            )

            margin = (
                candidates[0]["confidence_score"]
                - strongest_competitor_confidence
            )

        if (
            top_score >= SCORE_THRESHOLD
            and margin >= MARGIN_THRESHOLD
        ):
            prediction = (
                candidates[0]["item"]["item_code"]
            )

            source = "lexical"


    # --------------------------------------------------
    # Check AUTO result
    # --------------------------------------------------

    if prediction is None:
        continue

    correct = (
        bool(gt)
        and prediction == gt
    )

    if not correct:

        wrong_auto.append(
            {
                "line": line,
                "prediction": prediction,
                "source": source,
                "top_score": top_score,
                "margin": margin,
                "candidates": candidates,
            }
        )


print("=== WRONG AUTO MATCHES ===")
print("count:", len(wrong_auto))


for error in wrong_auto:

    line = error["line"]

    print()
    print("=" * 80)

    print("line_id:", line["line_id"])
    print("tenant:", line["tenant"])
    print("customer:", line["customer_id"])
    print("raw_text:", line["raw_text"])
    print("qty:", line["qty"])
    print("uom:", line["uom_text"])
    print("unit_price:", line["unit_price"])
    print("buyer_sku:", line["buyer_sku"])
    print("barcode:", line["raw_barcode"])
    print("notes:", line["notes"])

    print()
    print("GT:", line["gt_item_code"])
    print("PRED:", error["prediction"])
    print("source:", error["source"])
    print(
        "top_score:",
        round(error["top_score"], 4),
    )
    print(
        "margin:",
        round(error["margin"], 4),
    )

    print()
    print("TOP CANDIDATES")

    for position, candidate in enumerate(
        error["candidates"],
        start=1,
    ):

        item = candidate["item"]

        print()
        print(
            f"#{position}",
            item["item_code"],
        )

        print(
            "  name:",
            item["item_name"],
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
            "  confidence_score:",
            round(
                candidate["confidence_score"],
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

        print(
            "  description:",
            item["description"],
        )