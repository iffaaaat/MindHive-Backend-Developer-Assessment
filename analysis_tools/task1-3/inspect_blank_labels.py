from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


LINE_IDS = {
    "ACM-T-0015",
    "ACM-T-0114",
    "ACM-T-0130",
    "ACM-T-0150",
    "ACM-T-0177",
    "ACM-T-0212",
}


rows_by_id = {
    row["line_id"]: row
    for row in rows
}


for line_id in sorted(LINE_IDS):

    line = rows_by_id[line_id]

    print("=" * 90)

    print("LINE:", line_id)
    print("tenant:", line["tenant"])
    print("customer:", line["customer_id"])
    print("channel:", line["channel"])
    print("date:", line["order_date"])
    print("raw_text:", line["raw_text"])
    print("qty:", line["qty"])
    print("uom:", line["uom_text"])
    print("unit_price:", line["unit_price"])
    print("buyer_sku:", line["buyer_sku"])
    print("barcode:", line["raw_barcode"])
    print("notes:", line["notes"])
    print("GT:", repr(line["gt_item_code"]))

    print()

    barcode_match = matcher.resolve_barcode(line)
    alias_match = matcher.resolve_alias(line)

    print(
        "barcode resolution:",
        barcode_match["item_code"]
        if barcode_match
        else None,
    )

    print(
        "alias resolution:",
        alias_match["item_code"]
        if alias_match
        else None,
    )

    print()

    candidates = matcher.rank_candidates(
        line,
        limit=10,
        retrieval_limit=30,
    )

    print("TOP CANDIDATES")

    for position, candidate in enumerate(
        candidates,
        start=1,
    ):

        item = candidate["item"]

        print()
        print(
            f"#{position}",
            item["item_code"],
        )

        print(
            " name:",
            item["item_name"],
        )

        print(
            " description:",
            item["description"],
        )

        print(
            " lexical:",
            round(
                candidate["lexical_score"],
                4,
            ),
        )

        print(
            " numeric:",
            round(
                candidate["numeric_score"],
                4,
            ),
        )

        print(
            " brand:",
            candidate["brand_match"],
        )

        print(
            " score:",
            round(
                candidate["score"],
                4,
            ),
        )

        print(
            " stock_uom:",
            item["stock_uom"],
        )

        print(
            " conversions:",
            item["uom_conversions"],
        )

        print(
            " list_price:",
            item["list_price"],
        )

        print(
            " available_qty:",
            item["available_qty"],
        )

        print(
            " manufacturer_part_no:",
            item["manufacturer_part_no"],
        )

        print(
            " barcode:",
            item["barcode"],
        )

    print()