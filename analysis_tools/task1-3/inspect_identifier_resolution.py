from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


results = []


for line in rows:

    gt = line["gt_item_code"].strip()

    if not gt:
        continue


    # --------------------------------------------------
    # Strong identifier lane
    # --------------------------------------------------

    barcode_match = matcher.resolve_barcode(line)
    alias_match = matcher.resolve_alias(line)


    # --------------------------------------------------
    # Lexical lane
    # --------------------------------------------------

    candidates = matcher.rank_candidates(
        line,
        limit=20,
        retrieval_limit=50,
    )

    if not candidates:
        continue

    lexical_top = candidates[0]
    lexical_top_code = lexical_top["item"]["item_code"]

    # Only inspect lexical top-1 errors
    if lexical_top_code == gt:
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


    # --------------------------------------------------
    # Determine strong-identifier outcome
    # --------------------------------------------------

    identifier_prediction = None
    identifier_source = None
    identifier_conflict = False

    if barcode_match and alias_match:

        if (
            barcode_match["item_code"]
            == alias_match["item_code"]
        ):
            identifier_prediction = barcode_match["item_code"]
            identifier_source = "barcode+alias"

        else:
            identifier_conflict = True

    elif barcode_match:

        identifier_prediction = barcode_match["item_code"]
        identifier_source = "barcode"

    elif alias_match:

        identifier_prediction = alias_match["item_code"]
        identifier_source = "alias"


    results.append(
        {
            "line": line,
            "gt": gt,
            "gt_rank": gt_rank,
            "lexical_top": lexical_top,
            "identifier_prediction": identifier_prediction,
            "identifier_source": identifier_source,
            "identifier_conflict": identifier_conflict,
            "barcode_match": barcode_match,
            "alias_match": alias_match,
        }
    )


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("=== IDENTIFIER RESOLUTION ON LEXICAL ERRORS ===")
print("lexical top-1 errors:", len(results))

print()

identifier_correct = sum(
    result["identifier_prediction"] == result["gt"]
    for result in results
)

identifier_wrong = sum(
    (
        result["identifier_prediction"] is not None
        and result["identifier_prediction"] != result["gt"]
    )
    for result in results
)

identifier_none = sum(
    result["identifier_prediction"] is None
    for result in results
)

identifier_conflicts = sum(
    result["identifier_conflict"]
    for result in results
)

print(
    "identifier resolves correctly:",
    identifier_correct,
)

print(
    "identifier resolves incorrectly:",
    identifier_wrong,
)

print(
    "no identifier resolution:",
    identifier_none,
)

print(
    "barcode/alias conflicts:",
    identifier_conflicts,
)


# --------------------------------------------------
# Detailed rows
# --------------------------------------------------

print()
print("=== DETAILS ===")


for result in results:

    line = result["line"]
    top = result["lexical_top"]

    print()
    print("=" * 80)

    print(
        "line_id:",
        line["line_id"],
    )

    print(
        "raw_text:",
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

    print()

    print(
        "GT:",
        result["gt"],
    )

    print(
        "GT rank:",
        result["gt_rank"],
    )

    print()

    print(
        "alias_match:",
        (
            result["alias_match"]["item_code"]
            if result["alias_match"]
            else None
        ),
    )

    print(
        "barcode_match:",
        (
            result["barcode_match"]["item_code"]
            if result["barcode_match"]
            else None
        ),
    )

    print(
        "identifier_prediction:",
        result["identifier_prediction"],
    )

    print(
        "identifier_source:",
        result["identifier_source"],
    )

    print(
        "identifier_conflict:",
        result["identifier_conflict"],
    )

    print()

    print(
        "lexical_top:",
        top["item"]["item_code"],
    )

    print(
        "lexical_name:",
        top["item"]["item_name"],
    )

    print(
        "lexical_confidence:",
        round(
            top["confidence_score"],
            4,
        ),
    )

    print(
        "lexical_rank_score:",
        round(
            top["rank_score"],
            4,
        ),
    )

    # Simple diagnostic label
    print()

    if (
        result["identifier_prediction"]
        == result["gt"]
    ):

        print(
            "DIAGNOSIS:",
            "LEXICAL_ERROR_BUT_IDENTIFIER_CORRECT",
        )

    elif result["identifier_conflict"]:

        print(
            "DIAGNOSIS:",
            "IDENTIFIER_CONFLICT",
        )

    elif (
        result["identifier_prediction"] is not None
        and result["identifier_prediction"] != result["gt"]
    ):

        print(
            "DIAGNOSIS:",
            "IDENTIFIER_WRONG",
        )

    else:

        print(
            "DIAGNOSIS:",
            "TRUE_LEXICAL_CASE",
        )