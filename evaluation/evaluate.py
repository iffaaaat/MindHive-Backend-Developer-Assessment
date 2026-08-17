from collections import Counter, defaultdict

from src.data_loader import load_training_lines
from src.matcher import Matcher


AUTO_SCORE_THRESHOLD = 0.85
AUTO_MARGIN_THRESHOLD = 0.10
NO_MATCH_THRESHOLD = 0.70


def safe_divide(numerator, denominator):
    if denominator == 0:
        return 0.0

    return numerator / denominator


def evaluate():
    matcher = Matcher()
    rows = load_training_lines()

    total_rows = len(rows)

    labelled_rows = sum(
        bool(row["gt_item_code"].strip())
        for row in rows
    )

    blank_rows = (
        total_rows - labelled_rows
    )

    decision_counts = Counter()

    source_counts = Counter()

    auto_correct = 0
    auto_wrong = 0

    no_match_correct = 0
    no_match_wrong = 0

    review_positive = 0
    review_blank = 0

    top1_correct = 0
    top5_correct = 0

    strong_total = 0
    strong_correct = 0

    tenant_stats = defaultdict(
        lambda: {
            "rows": 0,
            "auto": 0,
            "auto_correct": 0,
            "auto_wrong": 0,
            "review": 0,
            "no_match": 0,
            "positive_gt": 0,
            "blank_gt": 0,
        }
    )

    wrong_auto_rows = []

    # --------------------------------------------------
    # Main evaluation loop
    # --------------------------------------------------

    for line in rows:

        tenant = line["tenant"]

        gt = line["gt_item_code"].strip()

        tenant_stats[tenant]["rows"] += 1

        if gt:
            tenant_stats[tenant][
                "positive_gt"
            ] += 1
        else:
            tenant_stats[tenant][
                "blank_gt"
            ] += 1


        # ----------------------------------------------
        # Retrieval quality
        #
        # Only meaningful where a labelled catalogue
        # target exists.
        # ----------------------------------------------

        if gt:

            candidates = matcher.rank_candidates(
                line,
                limit=5,
                retrieval_limit=30,
            )

            if candidates:

                top1_code = (
                    candidates[0]
                    ["item"]
                    ["item_code"]
                )

                top5_codes = [
                    candidate["item"]["item_code"]
                    for candidate in candidates
                ]

                if top1_code == gt:
                    top1_correct += 1

                if gt in top5_codes:
                    top5_correct += 1


        # ----------------------------------------------
        # Final decision
        # ----------------------------------------------

        result = matcher.decide(
            line,
            auto_score_threshold=(
                AUTO_SCORE_THRESHOLD
            ),
            auto_margin_threshold=(
                AUTO_MARGIN_THRESHOLD
            ),
            no_match_threshold=(
                NO_MATCH_THRESHOLD
            ),
        )

        decision = result["decision"]
        source = result["source"]

        decision_counts[decision] += 1
        source_counts[source] += 1


        # ----------------------------------------------
        # Strong signal quality
        # ----------------------------------------------

        if source in {
            "barcode",
            "alias",
            "barcode+alias",
        }:

            strong_total += 1

            if (
                gt
                and result["item_code"] == gt
            ):
                strong_correct += 1


        # ----------------------------------------------
        # AUTO
        # ----------------------------------------------

        if decision == "auto":

            tenant_stats[tenant]["auto"] += 1

            if (
                gt
                and result["item_code"] == gt
            ):

                auto_correct += 1

                tenant_stats[tenant][
                    "auto_correct"
                ] += 1

            else:

                auto_wrong += 1

                tenant_stats[tenant][
                    "auto_wrong"
                ] += 1

                wrong_auto_rows.append(
                    {
                        "line": line,
                        "result": result,
                    }
                )


        # ----------------------------------------------
        # REVIEW
        # ----------------------------------------------

        elif decision == "review":

            tenant_stats[tenant][
                "review"
            ] += 1

            if gt:
                review_positive += 1
            else:
                review_blank += 1


        # ----------------------------------------------
        # NO_MATCH
        # ----------------------------------------------

        elif decision == "no_match":

            tenant_stats[tenant][
                "no_match"
            ] += 1

            if not gt:
                no_match_correct += 1
            else:
                no_match_wrong += 1


    # --------------------------------------------------
    # Overall metrics
    # --------------------------------------------------

    auto_total = (
        auto_correct + auto_wrong
    )

    no_match_total = (
        no_match_correct + no_match_wrong
    )

    auto_precision = safe_divide(
        auto_correct,
        auto_total,
    )

    auto_coverage = safe_divide(
        auto_total,
        total_rows,
    )

    no_match_precision = safe_divide(
        no_match_correct,
        no_match_total,
    )

    no_match_blank_recall = safe_divide(
        no_match_correct,
        blank_rows,
    )

    top1_accuracy = safe_divide(
        top1_correct,
        labelled_rows,
    )

    top5_recall = safe_divide(
        top5_correct,
        labelled_rows,
    )

    strong_precision = safe_divide(
        strong_correct,
        strong_total,
    )


    # --------------------------------------------------
    # Report
    # --------------------------------------------------

    print(
        "========================================"
    )

    print(
        " MINDHIVE MATCHER EVALUATION"
    )

    print(
        "========================================"
    )

    print()

    print("Policy")
    print(
        "  AUTO score threshold :",
        AUTO_SCORE_THRESHOLD,
    )

    print(
        "  AUTO margin threshold:",
        AUTO_MARGIN_THRESHOLD,
    )

    print(
        "  NO_MATCH threshold   :",
        NO_MATCH_THRESHOLD,
    )

    print()


    print("Dataset")
    print("  total rows     :", total_rows)
    print("  labelled rows  :", labelled_rows)
    print("  blank GT rows  :", blank_rows)

    print()


    print("Retrieval / Ranking")

    print(
        "  top-1 accuracy :",
        f"{top1_correct}/{labelled_rows}",
        f"({top1_accuracy:.4f})",
    )

    print(
        "  top-5 recall   :",
        f"{top5_correct}/{labelled_rows}",
        f"({top5_recall:.4f})",
    )

    print()


    print("Strong identifiers")

    print(
        "  resolved       :",
        strong_total,
    )

    print(
        "  correct        :",
        strong_correct,
    )

    print(
        "  precision      :",
        f"{strong_precision:.4f}",
    )

    print()


    print("Three-way decisions")

    print(
        "  AUTO           :",
        decision_counts["auto"],
    )

    print(
        "  REVIEW         :",
        decision_counts["review"],
    )

    print(
        "  NO_MATCH       :",
        decision_counts["no_match"],
    )

    print()


    print("AUTO quality")

    print(
        "  correct        :",
        auto_correct,
    )

    print(
        "  wrong          :",
        auto_wrong,
    )

    print(
        "  precision      :",
        f"{auto_precision:.4f}",
    )

    print(
        "  coverage       :",
        f"{auto_coverage:.4f}",
    )

    print()


    print("REVIEW composition")

    print(
        "  positive GT    :",
        review_positive,
    )

    print(
        "  blank GT       :",
        review_blank,
    )

    print()


    print("NO_MATCH quality")

    print(
        "  correct blank  :",
        no_match_correct,
    )

    print(
        "  wrong positive :",
        no_match_wrong,
    )

    print(
        "  precision      :",
        f"{no_match_precision:.4f}",
    )

    print(
        "  blank recall   :",
        f"{no_match_blank_recall:.4f}",
    )

    print()


    print("Decision sources")

    for source, count in (
        source_counts.most_common()
    ):

        print(
            f"  {source:<20}:",
            count,
        )


    # --------------------------------------------------
    # Per-tenant report
    # --------------------------------------------------

    print()
    print("Per-tenant AUTO quality")


    for tenant in sorted(tenant_stats):

        stats = tenant_stats[tenant]

        tenant_auto = stats["auto"]

        tenant_precision = safe_divide(
            stats["auto_correct"],
            tenant_auto,
        )

        tenant_coverage = safe_divide(
            tenant_auto,
            stats["rows"],
        )

        print()

        print(
            f"  [{tenant}]"
        )

        print(
            "    rows          :",
            stats["rows"],
        )

        print(
            "    positive GT   :",
            stats["positive_gt"],
        )

        print(
            "    blank GT      :",
            stats["blank_gt"],
        )

        print(
            "    AUTO          :",
            stats["auto"],
        )

        print(
            "    AUTO correct  :",
            stats["auto_correct"],
        )

        print(
            "    AUTO wrong    :",
            stats["auto_wrong"],
        )

        print(
            "    AUTO precision:",
            f"{tenant_precision:.4f}",
        )

        print(
            "    AUTO coverage :",
            f"{tenant_coverage:.4f}",
        )

        print(
            "    REVIEW        :",
            stats["review"],
        )

        print(
            "    NO_MATCH      :",
            stats["no_match"],
        )


    # --------------------------------------------------
    # Cost-sensitive metric
    # --------------------------------------------------

    #
    # Assessment assumption:
    #
    # wrong automatic match cost ≈ 20x abstention.
    #
    # REVIEW and NO_MATCH are treated as abstentions
    # here for a simple relative-cost comparison.
    #

    abstentions = (
        decision_counts["review"]
        + decision_counts["no_match"]
    )

    relative_cost = (
        20 * auto_wrong
        + abstentions
    )


    print()
    print("Cost-sensitive summary")

    print(
        "  wrong AUTO     :",
        auto_wrong,
    )

    print(
        "  abstentions    :",
        abstentions,
    )

    print(
        "  relative cost  :",
        relative_cost,
    )


    # --------------------------------------------------
    # Residual AUTO errors
    # --------------------------------------------------

    print()
    print("Residual AUTO errors")

    if not wrong_auto_rows:

        print("  none")

    else:

        for row in wrong_auto_rows:

            line = row["line"]
            result = row["result"]

            print()

            print(
                " ",
                line["line_id"],
            )

            print(
                "    text:",
                line["raw_text"],
            )

            print(
                "    GT:",
                repr(
                    line["gt_item_code"]
                ),
            )

            print(
                "    prediction:",
                result["item_code"],
            )

            print(
                "    source:",
                result["source"],
            )

            print(
                "    confidence:",
                round(
                    result["confidence"],
                    4,
                ),
            )

            print(
                "    margin:",
                (
                    round(
                        result["margin"],
                        4,
                    )
                    if result["margin"]
                    is not None
                    else None
                ),
            )


if __name__ == "__main__":
    evaluate()