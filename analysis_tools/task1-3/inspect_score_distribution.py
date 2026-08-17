from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


positive_scores = []
blank_scores = []


for line in rows:

    candidates = matcher.rank_candidates(
        line,
        limit=20,
        retrieval_limit=30,
    )

    if not candidates:
        score = 0.0
        margin = 0.0

    else:
        top = candidates[0]

        score = top["confidence_score"]

        if len(candidates) >= 2:
            competitor = max(
                c["confidence_score"]
                for c in candidates[1:]
            )

            margin = score - competitor

        else:
            margin = score


    record = {
        "line": line,
        "score": score,
        "margin": margin,
    }


    if line["gt_item_code"].strip():
        positive_scores.append(record)
    else:
        blank_scores.append(record)


print("=== POSITIVE VS BLANK SCORE DISTRIBUTION ===")
print("positive:", len(positive_scores))
print("blank:", len(blank_scores))


thresholds = [
    0.30,
    0.40,
    0.50,
    0.60,
    0.70,
    0.75,
    0.80,
    0.85,
    0.90,
]


print()
print("=== SCORE >= THRESHOLD ===")

for threshold in thresholds:

    positives = sum(
        row["score"] >= threshold
        for row in positive_scores
    )

    blanks = sum(
        row["score"] >= threshold
        for row in blank_scores
    )

    print(
        f"{threshold:.2f}",
        "| positive:",
        f"{positives:3d}/{len(positive_scores)}",
        "| blank:",
        f"{blanks:3d}/{len(blank_scores)}",
    )


print()
print("=== SCORE < THRESHOLD ===")

for threshold in thresholds:

    positives = sum(
        row["score"] < threshold
        for row in positive_scores
    )

    blanks = sum(
        row["score"] < threshold
        for row in blank_scores
    )

    print(
        f"{threshold:.2f}",
        "| positive:",
        f"{positives:3d}/{len(positive_scores)}",
        "| blank:",
        f"{blanks:3d}/{len(blank_scores)}",
    )


print()
print("=== LOW-SCORING POSITIVE EXAMPLES ===")

lowest_positives = sorted(
    positive_scores,
    key=lambda row: row["score"],
)


for row in lowest_positives[:25]:

    line = row["line"]

    print()
    print(
        line["line_id"],
        "| score=",
        round(row["score"], 4),
        "| margin=",
        round(row["margin"], 4),
        "| GT=",
        line["gt_item_code"],
        "|",
        line["raw_text"],
    )