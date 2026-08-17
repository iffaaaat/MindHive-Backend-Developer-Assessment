import csv

from src.matcher import Matcher


TRAIN_PATH = "data/order_lines_train.csv"


def load_rows():
    with open(
        TRAIN_PATH,
        encoding="utf-8",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def main():

    matcher = Matcher()
    rows = load_rows()

    misses = []

    labelled_count = 0

    for line in rows:

        gt = line["gt_item_code"].strip()

        # Blank GT rows are not relevant for
        # positive retrieval recall.
        if not gt:
            continue

        labelled_count += 1

        # Ask for more than 5 so we can see whether
        # the GT is merely just outside top-5.
        candidates = matcher.rank_candidates(
            line,
            limit=20,
            retrieval_limit=30,
        )

        top5_codes = [
            candidate["item"]["item_code"]
            for candidate in candidates[:5]
        ]

        if gt not in top5_codes:

            gt_rank = None
            gt_candidate = None

            for index, candidate in enumerate(
                candidates,
                start=1,
            ):

                if (
                    candidate["item"]["item_code"]
                    == gt
                ):
                    gt_rank = index
                    gt_candidate = candidate
                    break

            misses.append(
                {
                    "line": line,
                    "candidates": candidates,
                    "gt_rank": gt_rank,
                    "gt_candidate": gt_candidate,
                }
            )


    print("=== TOP-5 RETRIEVAL MISSES ===")
    print("labelled rows:", labelled_count)
    print("misses:", len(misses))
    print()


    for miss in misses:

        line = miss["line"]
        candidates = miss["candidates"]
        gt_rank = miss["gt_rank"]
        gt_candidate = miss["gt_candidate"]

        print("=" * 80)

        print("line_id:", line["line_id"])
        print("tenant:", line["tenant"])
        print("customer:", line["customer_id"])
        print("raw_text:", line["raw_text"])
        print("qty:", line["qty"])
        print("uom:", line["uom_text"])
        print("unit_price:", line["unit_price"])
        print("buyer_sku:", line["buyer_sku"])
        print("barcode:", line["raw_barcode"])
        print("notes:", line["notes"])
        print()

        print("GT:", line["gt_item_code"])

        if gt_rank is None:
            print("GT rank: NOT IN TOP 20")
        else:
            print("GT rank:", gt_rank)

        print()

        print("TOP 5 CANDIDATES")
        print()

        for rank, candidate in enumerate(
            candidates[:5],
            start=1,
        ):

            item = candidate["item"]

            print(
                f"#{rank}",
                item["item_code"],
            )

            print(
                "  name:",
                item["item_name"],
            )

            print(
                "  lexical:",
                round(
                    candidate["lexical_score"],
                    4,
                ),
            )

            print(
                "  brand_match:",
                round(
                    candidate["brand_match"],
                    4,
                ),
            )

            print(
                "  numeric_score:",
                round(
                    candidate["numeric_score"],
                    4,
                ),
            )

            print(
                "  price_score:",
                round(
                    candidate["price_score"],
                    4,
                ),
            )

            print(
                "  rank_score:",
                round(
                    candidate["rank_score"],
                    4,
                ),
            )

            print(
                "  confidence_score:",
                round(
                    candidate["confidence_score"],
                    4,
                ),
            )

            print(
                "  stock_uom:",
                item["stock_uom"],
            )

            print(
                "  list_price:",
                item["list_price"],
            )

            print(
                "  description:",
                item["description"],
            )

            print()


        print("GROUND TRUTH CANDIDATE")
        print()

        if gt_candidate is None:

            print(
                "GT was not returned within "
                "the top 20 ranked candidates."
            )

        else:

            item = gt_candidate["item"]

            print(
                item["item_code"],
                item["item_name"],
            )

            print(
                "  rank:",
                gt_rank,
            )

            print(
                "  lexical:",
                round(
                    gt_candidate["lexical_score"],
                    4,
                ),
            )

            print(
                "  brand_match:",
                round(
                    gt_candidate["brand_match"],
                    4,
                ),
            )

            print(
                "  numeric_score:",
                round(
                    gt_candidate["numeric_score"],
                    4,
                ),
            )

            print(
                "  price_score:",
                round(
                    gt_candidate["price_score"],
                    4,
                ),
            )

            print(
                "  rank_score:",
                round(
                    gt_candidate["rank_score"],
                    4,
                ),
            )

            print(
                "  confidence_score:",
                round(
                    gt_candidate["confidence_score"],
                    4,
                ),
            )

            print(
                "  stock_uom:",
                item["stock_uom"],
            )

            print(
                "  list_price:",
                item["list_price"],
            )

            print(
                "  description:",
                item["description"],
            )

        print()


if __name__ == "__main__":
    main()