from rapidfuzz import fuzz

from src.data_loader import (
    load_catalogues,
    load_training_lines,
)
from src.normalizer import normalize_text


catalogues = load_catalogues()
rows = load_training_lines()


# --------------------------------------------------
# Prepare active catalogue items
# --------------------------------------------------

active_catalogues = {}

for tenant, items in catalogues.items():

    active_items = [
        item
        for item in items
        if item["disabled"] == "0"
    ]

    for item in active_items:

        item["_name"] = normalize_text(
            item["item_name"]
        )

        item["_description"] = normalize_text(
            item["description"]
        )

        item["_combined"] = normalize_text(
            " ".join(
                [
                    item["item_name"],
                    item["description"],
                    item["brand"],
                ]
            )
        )

    active_catalogues[tenant] = active_items


# --------------------------------------------------
# Retrieval methods to compare
# --------------------------------------------------

def wratio_combined(query, item):
    return fuzz.WRatio(
        query,
        item["_combined"],
    )


def wratio_name(query, item):
    return fuzz.WRatio(
        query,
        item["_name"],
    )


def token_set_name(query, item):
    return fuzz.token_set_ratio(
        query,
        item["_name"],
    )


def token_sort_name(query, item):
    return fuzz.token_sort_ratio(
        query,
        item["_name"],
    )


def max_name_score(query, item):
    """
    Take the best of several lexical comparisons
    against the product name.
    """

    return max(
        fuzz.WRatio(
            query,
            item["_name"],
        ),
        fuzz.token_set_ratio(
            query,
            item["_name"],
        ),
        fuzz.token_sort_ratio(
            query,
            item["_name"],
        ),
    )


METHODS = {
    "WRatio combined": wratio_combined,
    "WRatio name": wratio_name,
    "Token-set name": token_set_name,
    "Token-sort name": token_sort_name,
    "Max name scorers": max_name_score,
}


# --------------------------------------------------
# Evaluate each retrieval method
# --------------------------------------------------

for method_name, scoring_function in METHODS.items():

    top1_correct = 0
    top5_correct = 0
    evaluated = 0

    for line in rows:

        gt = line["gt_item_code"].strip()

        # Retrieval recall is measured only on lines
        # where a correct catalogue item exists.
        if not gt:
            continue

        evaluated += 1

        tenant = line["tenant"]

        query = normalize_text(
            line["raw_text"]
        )

        candidates = []

        for item in active_catalogues[tenant]:

            score = scoring_function(
                query,
                item,
            )

            candidates.append(
                (
                    score,
                    item["item_code"],
                )
            )

        candidates.sort(
            key=lambda candidate: candidate[0],
            reverse=True,
        )

        top5_codes = [
            item_code
            for score, item_code
            in candidates[:5]
        ]

        if top5_codes[0] == gt:
            top1_correct += 1

        if gt in top5_codes:
            top5_correct += 1


    print()
    print(
        "===",
        method_name,
        "===",
    )

    print(
        "top-1:",
        top1_correct,
        "/",
        evaluated,
        "=",
        round(
            top1_correct / evaluated,
            4,
        ),
    )

    print(
        "top-5:",
        top5_correct,
        "/",
        evaluated,
        "=",
        round(
            top5_correct / evaluated,
            4,
        ),
    )