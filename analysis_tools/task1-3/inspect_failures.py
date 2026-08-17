from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


# A selection of interesting failures from the latest evaluation.
FAILURE_IDS = {
    "ACM-T-0071",
    "ACM-T-0166",
    "ACM-T-0179",
    "ACM-T-0209",
    "ACM-T-0249",
    "NRD-T-0009",
}


rows_by_id = {
    row["line_id"]: row
    for row in rows
}


def print_item(label, item):
    print(label)
    print("  code:", item["item_code"])
    print("  name:", item["item_name"])
    print("  brand:", item["brand"])
    print("  group:", item["item_group"])
    print("  stock_uom:", item["stock_uom"])
    print("  conversions:", item["uom_conversions"])
    print("  barcode:", item["barcode"])
    print(
        "  manufacturer_part_no:",
        item["manufacturer_part_no"],
    )
    print("  price:", item["list_price"])
    print()


for line_id in FAILURE_IDS:

    line = rows_by_id[line_id]

    gt_code = line["gt_item_code"]

    print("=" * 80)
    print("LINE:", line_id)
    print("raw_text:", line["raw_text"])
    print("qty:", line["qty"])
    print("uom_text:", line["uom_text"])
    print("unit_price:", line["unit_price"])
    print("buyer_sku:", line["buyer_sku"])
    print("barcode:", line["raw_barcode"])
    print("notes:", line["notes"])
    print("GT:", gt_code)
    print()

    gt_item = matcher.item_lookup[
        line["tenant"]
    ].get(gt_code)

    if gt_item:
        print_item(
            "GROUND TRUTH ITEM",
            gt_item,
        )

    candidates = matcher.rank_candidates(
        line,
        limit=5,
        retrieval_limit=20,
    )

    print("TOP 5 CANDIDATES")

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
            "  brand:",
            candidate["brand_match"],
        )

        print(
            "  numeric:",
            round(
                candidate["numeric_score"],
                4,
            ),
        )

        print(
            "  final:",
            round(
                candidate["score"],
                4,
            ),
        )

        print(
            "  stock_uom:",
            item["stock_uom"],
        )

        print(
            "  conversions:",
            item["uom_conversions"],
        )

        print(
            "  price:",
            item["list_price"],
        )

    if len(candidates) >= 2:

        margin = (
            candidates[0]["score"]
            - candidates[1]["score"]
        )

        print()
        print(
            "TOP1-TOP2 MARGIN:",
            round(
                margin,
                4,
            ),
        )

    print()