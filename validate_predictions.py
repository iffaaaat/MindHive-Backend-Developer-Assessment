import csv


PREDICTIONS_FILE = "predictions.csv"

EXPECTED_COLUMNS = [
    "line_id",
    "item_code",
    "confidence",
    "decision",
    "reason_code",
    "candidates",
]

ALLOWED_DECISIONS = {
    "auto",
    "review",
    "reject",
}


with open(
    PREDICTIONS_FILE,
    mode="r",
    encoding="utf-8",
    newline="",
) as file:

    reader = csv.DictReader(file)

    assert reader.fieldnames == EXPECTED_COLUMNS, (
        f"Wrong columns.\n"
        f"Expected: {EXPECTED_COLUMNS}\n"
        f"Actual:   {reader.fieldnames}"
    )

    rows = list(reader)


errors = []
seen_line_ids = set()


for row in rows:

    line_id = row["line_id"]
    item_code = row["item_code"]
    decision = row["decision"]

    # ----------------------------------------------
    # Unique line IDs
    # ----------------------------------------------

    if line_id in seen_line_ids:
        errors.append(
            f"{line_id}: duplicate line_id"
        )

    seen_line_ids.add(line_id)


    # ----------------------------------------------
    # Decision
    # ----------------------------------------------

    if decision not in ALLOWED_DECISIONS:
        errors.append(
            f"{line_id}: invalid decision "
            f"{decision!r}"
        )


    # ----------------------------------------------
    # Confidence
    # ----------------------------------------------

    try:
        confidence = float(row["confidence"])

        if not 0.0 <= confidence <= 1.0:
            errors.append(
                f"{line_id}: confidence outside "
                f"[0,1]: {confidence}"
            )

    except ValueError:
        errors.append(
            f"{line_id}: invalid confidence "
            f"{row['confidence']!r}"
        )


    # ----------------------------------------------
    # Abstention contract
    # ----------------------------------------------

    if decision == "auto" and not item_code:
        errors.append(
            f"{line_id}: AUTO has blank item_code"
        )

    if decision in {"review", "reject"} and item_code:
        errors.append(
            f"{line_id}: abstention has populated "
            f"item_code {item_code}"
        )


    # ----------------------------------------------
    # Candidate format / maximum 3
    # ----------------------------------------------

    candidates = [
        candidate
        for candidate in row["candidates"].split("|")
        if candidate
    ]

    if len(candidates) > 3:
        errors.append(
            f"{line_id}: more than 3 candidates"
        )

    for candidate in candidates:

        if ":" not in candidate:
            errors.append(
                f"{line_id}: malformed candidate "
                f"{candidate!r}"
            )
            continue

        code, score_text = candidate.rsplit(":", 1)

        try:
            score = float(score_text)

            if not 0.0 <= score <= 1.0:
                errors.append(
                    f"{line_id}: candidate score "
                    f"outside [0,1]: {candidate}"
                )

        except ValueError:
            errors.append(
                f"{line_id}: invalid candidate "
                f"score: {candidate}"
            )


    # ----------------------------------------------
    # Tenant isolation sanity check
    # ----------------------------------------------

    if line_id.startswith("ACM-"):
        expected_prefix = "ACM-"

    elif line_id.startswith("NRD-"):
        expected_prefix = "NRD-"

    else:
        expected_prefix = None


    codes_to_check = []

    if item_code:
        codes_to_check.append(item_code)

    for candidate in candidates:
        if ":" in candidate:
            code, _ = candidate.rsplit(":", 1)
            codes_to_check.append(code)


    if expected_prefix:

        for code in codes_to_check:

            if not code.startswith(expected_prefix):
                errors.append(
                    f"{line_id}: cross-tenant code "
                    f"{code}"
                )


print("=== PREDICTIONS VALIDATION ===")
print("rows:", len(rows))
print("unique line_ids:", len(seen_line_ids))
print("errors:", len(errors))
print()


if len(rows) != 300:
    print(
        f"FAIL: expected 300 rows, "
        f"found {len(rows)}"
    )
else:
    print("PASS: exactly 300 prediction rows")


if errors:

    print()
    print("VALIDATION ERRORS")

    for error in errors:
        print("-", error)

else:

    print(
        "PASS: schema and row-level "
        "validation succeeded"
    )