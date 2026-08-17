from collections import Counter

from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


decision_counts = Counter()

auto_correct = 0
auto_wrong = 0

review_positive = 0
review_blank = 0

no_match_correct = 0
no_match_wrong = 0

wrong_auto_rows = []
wrong_no_match_rows = []


for line in rows:

    gt = line["gt_item_code"].strip()

    result = matcher.decide(line)

    decision = result["decision"]

    decision_counts[decision] += 1


    # --------------------------------------------------
    # AUTO
    # --------------------------------------------------

    if decision == "auto":

        if (
            gt
            and result["item_code"] == gt
        ):

            auto_correct += 1

        else:

            auto_wrong += 1

            wrong_auto_rows.append(
                {
                    "line": line,
                    "result": result,
                }
            )


    # --------------------------------------------------
    # REVIEW
    # --------------------------------------------------

    elif decision == "review":

        if gt:
            review_positive += 1
        else:
            review_blank += 1


    # --------------------------------------------------
    # NO_MATCH
    # --------------------------------------------------

    elif decision == "no_match":

        if not gt:

            no_match_correct += 1

        else:

            no_match_wrong += 1

            wrong_no_match_rows.append(
                {
                    "line": line,
                    "result": result,
                }
            )


# --------------------------------------------------
# Summary metrics
# --------------------------------------------------

total = len(rows)

auto_total = (
    auto_correct + auto_wrong
)

no_match_total = (
    no_match_correct + no_match_wrong
)


auto_precision = (
    auto_correct / auto_total
    if auto_total
    else 0.0
)

auto_coverage = (
    auto_total / total
)

no_match_precision = (
    no_match_correct / no_match_total
    if no_match_total
    else 0.0
)


blank_total = sum(
    not row["gt_item_code"].strip()
    for row in rows
)

no_match_recall = (
    no_match_correct / blank_total
    if blank_total
    else 0.0
)


print("=== THREE-WAY DECISION EVALUATION ===")

print("total rows:", total)

print()

print("AUTO:", decision_counts["auto"])
print("REVIEW:", decision_counts["review"])
print("NO_MATCH:", decision_counts["no_match"])

print()


print("=== AUTO QUALITY ===")

print("correct:", auto_correct)
print("wrong:", auto_wrong)

print(
    "precision:",
    round(auto_precision, 4),
)

print(
    "coverage:",
    round(auto_coverage, 4),
)


print()
print("=== REVIEW COMPOSITION ===")

print(
    "positive GT:",
    review_positive,
)

print(
    "blank GT:",
    review_blank,
)


print()
print("=== NO_MATCH QUALITY ===")

print(
    "correct blank GT:",
    no_match_correct,
)

print(
    "wrong positive GT:",
    no_match_wrong,
)

print(
    "precision:",
    round(no_match_precision, 4),
)

print(
    "blank-GT recall:",
    round(no_match_recall, 4),
)


# --------------------------------------------------
# Wrong AUTO examples
# --------------------------------------------------

print()
print("=== WRONG AUTO ===")

for row in wrong_auto_rows:

    line = row["line"]
    result = row["result"]

    print()

    print(
        line["line_id"],
        "| text=",
        line["raw_text"],
    )

    print(
        "GT=",
        repr(line["gt_item_code"]),
        "| pred=",
        result["item_code"],
        "| source=",
        result["source"],
        "| confidence=",
        round(result["confidence"], 4),
        "| margin=",
        (
            round(result["margin"], 4)
            if result["margin"] is not None
            else None
        ),
    )


# --------------------------------------------------
# Wrong NO_MATCH examples
# --------------------------------------------------

print()
print("=== WRONG NO_MATCH ===")

for row in wrong_no_match_rows:

    line = row["line"]
    result = row["result"]

    print()

    print(
        line["line_id"],
        "| text=",
        line["raw_text"],
    )

    print(
        "GT=",
        line["gt_item_code"],
        "| confidence=",
        round(result["confidence"], 4),
        "| margin=",
        round(result["margin"], 4),
    )