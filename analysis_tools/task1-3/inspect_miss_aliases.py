from src.data_loader import (
    load_training_lines,
    load_customer_sku_map,
)
from src.matcher import Matcher


LINE_IDS = {
    "ACM-T-0132",
    "ACM-T-0133",
    "ACM-T-0255",
}


rows = load_training_lines()
aliases = load_customer_sku_map()
matcher = Matcher()


rows_by_id = {
    row["line_id"]: row
    for row in rows
}


for line_id in sorted(LINE_IDS):

    line = rows_by_id[line_id]

    tenant = line["tenant"]
    customer_id = line["customer_id"]
    buyer_sku = line["buyer_sku"].strip()
    order_date = line["order_date"]

    print("=" * 90)

    print("line_id:", line_id)
    print("raw_text:", line["raw_text"])
    print("GT:", line["gt_item_code"])
    print("tenant:", tenant)
    print("customer:", customer_id)
    print("buyer_sku:", buyer_sku)
    print("order_date:", order_date)

    print()

    resolved = matcher.resolve_alias(line)

    print(
        "CURRENT resolve_alias RESULT:",
        resolved["item_code"]
        if resolved
        else None,
    )

    print()

    # Exact tenant + customer + SKU records
    exact_records = [
        alias
        for alias in aliases
        if (
            alias["tenant"] == tenant
            and alias["customer_id"] == customer_id
            and alias["customer_sku"] == buyer_sku
        )
    ]

    print(
        "EXACT tenant/customer/SKU records:",
        len(exact_records),
    )

    for alias in exact_records:

        item = matcher.item_lookup[
            tenant
        ].get(
            alias["item_code"]
        )

        print()
        print("  item_code:", alias["item_code"])

        print(
            "  item_name:",
            item["item_name"]
            if item
            else "NOT ACTIVE / NOT FOUND",
        )

        print(
            "  customer_description:",
            alias["customer_description"],
        )

        print(
            "  source:",
            alias["source"],
        )

        print(
            "  confidence:",
            alias["confidence"],
        )

        print(
            "  valid_from:",
            alias["valid_from"],
        )

        print(
            "  valid_to:",
            alias["valid_to"],
        )

        is_date_valid = True

        if (
            alias["valid_from"]
            and order_date < alias["valid_from"]
        ):
            is_date_valid = False

        if (
            alias["valid_to"]
            and order_date > alias["valid_to"]
        ):
            is_date_valid = False

        print(
            "  valid_on_order_date:",
            is_date_valid,
        )

        print(
            "  points_to_GT:",
            alias["item_code"]
            == line["gt_item_code"],
        )


    # Also inspect same SKU elsewhere, because the
    # mapping may exist under another customer or tenant.
    same_sku_records = [
        alias
        for alias in aliases
        if alias["customer_sku"] == buyer_sku
    ]

    print()
    print(
        "ALL records with same customer_sku:",
        len(same_sku_records),
    )

    for alias in same_sku_records:

        print(
            " ",
            alias["tenant"],
            alias["customer_id"],
            alias["customer_sku"],
            "->",
            alias["item_code"],
            "| source=",
            alias["source"],
            "| confidence=",
            alias["confidence"],
            "| valid_to=",
            repr(alias["valid_to"]),
        )

    print()