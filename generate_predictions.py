import csv

from src.data_loader import load_holdout_lines
from src.matcher import Matcher


OUTPUT_FILE = "predictions.csv"


def make_reason_code(result):
    source = result["source"]
    decision = result["decision"]

    if source == "barcode+alias":
        return "identifier_agree"

    if source == "barcode":
        return "barcode_hit"

    if source == "alias":
        return "alias_exact"

    if source == "identifier_conflict":
        return "identifier_conflict"

    if source == "lexical":

        if decision == "auto":
            return "lexical_unique"

        if decision == "review":
            return "lexical_ambiguous"

        if decision == "no_match":
            return "no_candidate_above_floor"

    return "unknown"


def format_candidates(result):
    candidates = result["candidates"]

    if candidates:

        formatted = []

        for candidate in candidates[:3]:

            item_code = candidate["item"]["item_code"]
            score = candidate["rank_score"]

            formatted.append(
                f"{item_code}:{score:.4f}"
            )

        return "|".join(formatted)

    # Strong identifier matches do not currently carry
    # ranked lexical candidates, but the resolved item
    # itself is still valid candidate evidence.
    if (
        result["decision"] == "auto"
        and result["item_code"]
    ):
        return (
            f"{result['item_code']}:"
            f"{result['confidence']:.4f}"
        )

    return ""


matcher = Matcher()
rows = load_holdout_lines()


with open(
    OUTPUT_FILE,
    mode="w",
    encoding="utf-8",
    newline="",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "line_id",
            "item_code",
            "confidence",
            "decision",
            "reason_code",
            "candidates",
        ],
    )

    writer.writeheader()

    for line in rows:

        result = matcher.decide(line)

        internal_decision = result["decision"]

        # --------------------------------------------------
        # Convert internal matcher terminology into the
        # submission schema required by the assessment.
        # --------------------------------------------------

        if internal_decision == "auto":
            output_decision = "auto"
            output_item_code = result["item_code"]

        elif internal_decision == "review":
            output_decision = "review"

            # REVIEW is an abstention in the submission
            # format, so item_code must be blank.
            output_item_code = ""

        else:
            # Internal "no_match" maps to required "reject".
            output_decision = "reject"
            output_item_code = ""

        writer.writerow(
            {
                "line_id": line["line_id"],
                "item_code": output_item_code,
                "confidence": f"{result['confidence']:.4f}",
                "decision": output_decision,
                "reason_code": make_reason_code(result),
                "candidates": format_candidates(result),
            }
        )


print(
    f"Wrote {len(rows)} predictions to "
    f"{OUTPUT_FILE}"
)