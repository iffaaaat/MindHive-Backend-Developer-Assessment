from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


TARGET_LINE_ID = "NRD-T-0009"


for line in rows:

    if line["line_id"] != TARGET_LINE_ID:
        continue

    tenant = line["tenant"]
    barcode = line["raw_barcode"].strip()

    print("=== BARCODE INVESTIGATION ===")
    print("line_id:", line["line_id"])
    print("tenant:", tenant)
    print("raw barcode:", barcode)
    print("GT:", line["gt_item_code"])

    print()

    matches = matcher.barcode_lookup[
        tenant
    ].get(
        barcode,
        [],
    )

    print("barcode lookup match count:", len(matches))

    print()

    for position, item in enumerate(
        matches,
        start=1,
    ):
        print("=" * 80)
        print("MATCH", position)
        print("item_code:", item["item_code"])
        print("item_name:", item["item_name"])
        print("barcode:", item["barcode"])
        print("stock_uom:", item["stock_uom"])
        print("list_price:", item["list_price"])

    print()
    print(
        "resolve_barcode result:",
        matcher.resolve_barcode(line),
    )

    break