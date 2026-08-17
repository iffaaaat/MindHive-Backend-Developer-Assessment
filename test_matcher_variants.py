from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()

rows_by_id = {
    row["line_id"]: row
    for row in rows
}


TESTS = [
    (
        "ACM-T-0071",
        "ACM-ANGL0444",
        "Tolsen Angle Grinder Disc 4.5\" Flap",
    ),
    (
        "ACM-T-0166",
        "ACM-ANGL1068",
        "Bosco Angle Grinder Disc 5\" Flap",
    ),
]


for line_id, expected_code, expected_name in TESTS:

    print("=" * 70)
    print("LINE:", line_id)

    line = rows_by_id[line_id]

    candidates = matcher.rank_candidates(
        line,
        limit=5,
        retrieval_limit=30,
    )

    assert candidates, (
        f"No candidates returned for {line_id}"
    )

    top = candidates[0]

    actual_code = top["item"]["item_code"]
    actual_name = top["item"]["item_name"]

    print("RAW TEXT:", line["raw_text"])
    print("EXPECTED:", expected_code, expected_name)
    print("ACTUAL:", actual_code, actual_name)
    print("RANK SCORE:", round(top["rank_score"], 4))
    print(
        "VARIANT SCORE:",
        top.get("variant_score"),
    )

    assert actual_code == expected_code, (
        f"\nVariant reranking failed"
        f"\nLine:     {line_id}"
        f"\nExpected: {expected_code} - {expected_name}"
        f"\nActual:   {actual_code} - {actual_name}"
    )

    print("PASS")
    print()


print("=" * 70)
print(
    f"ALL {len(TESTS)} VARIANT RANKING TESTS PASSED"
)