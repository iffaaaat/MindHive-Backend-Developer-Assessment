from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


# --------------------------------------------------
# Thresholds to test
# --------------------------------------------------

SCORE_THRESHOLDS = [
    0.85,
    0.90,
    0.925,
    0.95,
    0.97,
    0.98,
]

MARGIN_THRESHOLDS = [
    0.00,
    0.01,
    0.03,
    0.05,
    0.10,
]


# --------------------------------------------------
# Pre-compute predictions once
# --------------------------------------------------

evaluated_rows = []


for line in rows:

    gt = line["gt_item_code"].strip()

    barcode_match = matcher.resolve_barcode(line)
    alias_match = matcher.resolve_alias(line)

    strong_prediction = None
    strong_source = None


    # -----------------------------------
    # Strong identifier lane
    # -----------------------------------

    if barcode_match and alias_match:

        if (
            barcode_match["item_code"]
            == alias_match["item_code"]
        ):
            strong_prediction = (
                barcode_match["item_code"]
            )

            strong_source = (
                "barcode+alias"
            )

        # If they contradict, deliberately leave the
        # prediction unresolved.

    elif barcode_match:

        strong_prediction = (
            barcode_match["item_code"]
        )

        strong_source = "barcode"

    elif alias_match:

        strong_prediction = (
            alias_match["item_code"]
        )

        strong_source = "alias"


    # -----------------------------------
    # Lexical candidates
    # -----------------------------------

    candidates = matcher.rank_candidates(
    line,
    limit=20,
    retrieval_limit=30,
    )

    lexical_prediction = None
    top_score = 0.0
    margin = 0.0


    if candidates:

        # Candidate #1 is selected by rank_score,
        # which may include price.
        chosen = candidates[0]

        lexical_prediction = (
            chosen["item"]["item_code"]
        )

        top_score = (
            chosen["confidence_score"]
        )


        # -----------------------------------
        # Confidence margin
        #
        # Compare the chosen candidate against
        # the strongest confidence competitor,
        # NOT simply rank position #2.
        # -----------------------------------

        if len(candidates) >= 2:

            strongest_competitor_confidence = max(
                candidate["confidence_score"]
                for candidate in candidates[1:]
            )

            margin = (
                chosen["confidence_score"]
                - strongest_competitor_confidence
            )


    evaluated_rows.append(
        {
            "line_id": line["line_id"],
            "gt": gt,
            "strong_prediction": strong_prediction,
            "strong_source": strong_source,
            "lexical_prediction": lexical_prediction,
            "top_score": top_score,
            "margin": margin,
        }
    )


# --------------------------------------------------
# Evaluate threshold combinations
# --------------------------------------------------

print(
    "=== AUTO-MATCH PRECISION / COVERAGE SWEEP ==="
)

print(
    "Total rows:",
    len(evaluated_rows),
)

print()


for score_threshold in SCORE_THRESHOLDS:

    for margin_threshold in MARGIN_THRESHOLDS:

        auto_count = 0
        correct = 0
        wrong = 0
        strong_count = 0
        lexical_count = 0


        for row in evaluated_rows:

            prediction = None


            # -----------------------------------
            # Strong identifier matches
            # -----------------------------------

            if row["strong_prediction"]:

                prediction = (
                    row["strong_prediction"]
                )

                strong_count += 1


            # -----------------------------------
            # Lexical auto-match
            # -----------------------------------

            elif (
                row["lexical_prediction"]
                and row["top_score"]
                    >= score_threshold
                and row["margin"]
                    >= margin_threshold
            ):

                prediction = (
                    row["lexical_prediction"]
                )

                lexical_count += 1


            # No auto decision.
            if prediction is None:
                continue


            auto_count += 1


            # Blank GT means the correct behaviour was
            # to abstain. Any automatic catalogue item
            # is therefore a false positive.
            if (
                row["gt"]
                and prediction == row["gt"]
            ):

                correct += 1

            else:

                wrong += 1


        precision = (
            correct / auto_count
            if auto_count
            else 0.0
        )

        coverage = (
            auto_count / len(evaluated_rows)
        )


        print(
            f"score>={score_threshold:.3f}",
            f"margin>={margin_threshold:.2f}",
            f"auto={auto_count:3d}",
            f"correct={correct:3d}",
            f"wrong={wrong:3d}",
            f"precision={precision:.4f}",
            f"coverage={coverage:.4f}",
            f"strong={strong_count:2d}",
            f"lexical={lexical_count:3d}",
        )

    print()