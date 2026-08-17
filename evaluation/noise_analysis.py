import re
from collections import Counter, defaultdict

from src.data_loader import load_training_lines
from src.matcher import Matcher


def detect_noise_patterns(line):
    """
    Assign lightweight, interpretable noise tags.

    A line may have multiple tags.
    These are diagnostic labels only; they do not
    affect matching decisions.
    """

    text = line["raw_text"]
    lower = text.lower()

    tags = set()

    # -----------------------------------
    # Very short / underspecified text
    # -----------------------------------

    token_count = len(
        re.findall(r"\w+", text)
    )

    if token_count <= 3:
        tags.add("short_text")


    # -----------------------------------
    # Conversational/order noise
    # -----------------------------------

    if re.search(
        r"\b(?:pls|please|urgent|need|send|thanks|bro)\b",
        lower,
    ):
        tags.add("conversational_noise")


    # -----------------------------------
    # Separator-heavy formatting
    # -----------------------------------

    if re.search(
        r"[/_|]",
        text,
    ):
        tags.add("separator_noise")


    # -----------------------------------
    # Suspicious repeated whitespace
    # -----------------------------------

    if re.search(
        r"\s{2,}",
        text,
    ):
        tags.add("spacing_noise")


    # -----------------------------------
    # Measurement / numeric attributes
    # -----------------------------------

    if re.search(
        r"\d",
        text,
    ):
        tags.add("numeric_attributes")


    # -----------------------------------
    # Obvious malformed-looking dimensions
    #
    # Examples observed in training:
    # 05mm, 3700mm, 1100mm, misplaced quotes.
    # This is intentionally broad and diagnostic.
    # -----------------------------------

    if re.search(
        r'\d+\s*["\']',
        text,
    ) or re.search(
        r"\d+\s*(?:mm|kg|g|l)\b",
        lower,
    ):
        tags.add("measurement_text")


    # -----------------------------------
    # Buyer identifier availability
    # -----------------------------------

    if line["buyer_sku"].strip():
        tags.add("has_buyer_sku")


    if line["raw_barcode"].strip():
        tags.add("has_barcode")


    if line["unit_price"].strip():
        tags.add("has_price")


    if line["uom_text"].strip():
        tags.add("has_uom")


    if not tags:
        tags.add("plain_text")

    return tags


def safe_divide(a, b):
    return a / b if b else 0.0


def main():

    matcher = Matcher()
    rows = load_training_lines()

    stats = defaultdict(
        lambda: {
            "rows": 0,
            "positive": 0,
            "blank": 0,
            "auto": 0,
            "auto_correct": 0,
            "auto_wrong": 0,
            "review": 0,
            "no_match": 0,
            "top1_correct": 0,
            "top5_correct": 0,
        }
    )


    for line in rows:

        gt = line["gt_item_code"].strip()

        tags = detect_noise_patterns(line)


        # -----------------------------------
        # Retrieval result
        # -----------------------------------

        candidates = matcher.rank_candidates(
            line,
            limit=5,
            retrieval_limit=30,
        )

        top1_correct = False
        top5_correct = False

        if gt and candidates:

            top1_code = (
                candidates[0]["item"]["item_code"]
            )

            top5_codes = [
                candidate["item"]["item_code"]
                for candidate in candidates
            ]

            top1_correct = (
                top1_code == gt
            )

            top5_correct = (
                gt in top5_codes
            )


        # -----------------------------------
        # Final decision
        # -----------------------------------

        result = matcher.decide(line)


        for tag in tags:

            s = stats[tag]

            s["rows"] += 1

            if gt:
                s["positive"] += 1
            else:
                s["blank"] += 1

            if top1_correct:
                s["top1_correct"] += 1

            if top5_correct:
                s["top5_correct"] += 1


            if result["decision"] == "auto":

                s["auto"] += 1

                if (
                    gt
                    and result["item_code"] == gt
                ):
                    s["auto_correct"] += 1
                else:
                    s["auto_wrong"] += 1


            elif result["decision"] == "review":
                s["review"] += 1


            elif result["decision"] == "no_match":
                s["no_match"] += 1


    print(
        "========================================"
    )
    print(
        " NOISE PATTERN ANALYSIS"
    )
    print(
        "========================================"
    )


    ordered_tags = sorted(
        stats,
        key=lambda tag:
            stats[tag]["rows"],
        reverse=True,
    )


    for tag in ordered_tags:

        s = stats[tag]

        positive = s["positive"]

        top1 = safe_divide(
            s["top1_correct"],
            positive,
        )

        top5 = safe_divide(
            s["top5_correct"],
            positive,
        )

        auto_precision = safe_divide(
            s["auto_correct"],
            s["auto"],
        )

        auto_coverage = safe_divide(
            s["auto"],
            s["rows"],
        )


        print()
        print(
            f"[{tag}]"
        )

        print(
            "  rows           :",
            s["rows"],
        )

        print(
            "  positive GT    :",
            s["positive"],
        )

        print(
            "  blank GT       :",
            s["blank"],
        )

        print(
            "  top-1 accuracy :",
            f"{top1:.4f}",
        )

        print(
            "  top-5 recall   :",
            f"{top5:.4f}",
        )

        print(
            "  AUTO           :",
            s["auto"],
        )

        print(
            "  AUTO correct   :",
            s["auto_correct"],
        )

        print(
            "  AUTO wrong     :",
            s["auto_wrong"],
        )

        print(
            "  AUTO precision :",
            f"{auto_precision:.4f}",
        )

        print(
            "  AUTO coverage  :",
            f"{auto_coverage:.4f}",
        )

        print(
            "  REVIEW         :",
            s["review"],
        )

        print(
            "  NO_MATCH       :",
            s["no_match"],
        )


if __name__ == "__main__":
    main()