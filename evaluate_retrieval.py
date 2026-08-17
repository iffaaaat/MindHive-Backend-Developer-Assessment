from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


nonblank_gt = 0
top1_correct = 0
top5_correct = 0

scores_correct = []
scores_wrong = []

failures = []


for line in rows:
    gt = line["gt_item_code"].strip()

    if not gt:
        continue

    nonblank_gt += 1

    candidates = matcher.rank_candidates(
        line,
        limit=5,
    )

    if not candidates:
        continue

    top1 = candidates[0]

    top1_code = top1["item"]["item_code"]

    top5_codes = [
        candidate["item"]["item_code"]
        for candidate in candidates
    ]

    if top1_code == gt:
        top1_correct += 1
        scores_correct.append(
            top1["score"]
        )

    else:
        scores_wrong.append(
            top1["score"]
        )

        failures.append(
            {
                "line_id": line["line_id"],
                "text": line["raw_text"],
                "gt": gt,
                "pred": top1_code,
                "score": top1["score"],
                "top5": top5_codes,
            }
        )

    if gt in top5_codes:
        top5_correct += 1


print("=== LEXICAL RETRIEVAL ===")

print(
    "nonblank GT:",
    nonblank_gt,
)

print(
    "top-1:",
    top1_correct,
    "/",
    nonblank_gt,
    "=",
    round(
        top1_correct / nonblank_gt,
        4,
    ),
)

print(
    "top-5:",
    top5_correct,
    "/",
    nonblank_gt,
    "=",
    round(
        top5_correct / nonblank_gt,
        4,
    ),
)


if scores_correct:
    print(
        "avg correct top1 score:",
        round(
            sum(scores_correct)
            / len(scores_correct),
            4,
        ),
    )


if scores_wrong:
    print(
        "avg wrong top1 score:",
        round(
            sum(scores_wrong)
            / len(scores_wrong),
            4,
        ),
    )


print(
    "\n=== FIRST 20 TOP-1 FAILURES ==="
)

for failure in failures[:20]:
    print()

    print(
        "line:",
        failure["line_id"],
    )

    print(
        "text:",
        failure["text"],
    )

    print(
        "GT:",
        failure["gt"],
    )

    print(
        "pred:",
        failure["pred"],
    )

    print(
        "score:",
        round(
            failure["score"],
            4,
        ),
    )

    print(
        "top5:",
        failure["top5"],
    )