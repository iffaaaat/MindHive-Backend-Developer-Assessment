import re

from src.matcher import Matcher
from src.data_loader import load_training_lines
from src.normalizer import normalize_text


matcher = Matcher()
rows = load_training_lines()


def is_bulk(item):
    name = normalize_text(item["item_name"])
    return bool(
        re.search(r"\bbulk\b", name)
    )


print("=== POSITIVE GT BASE / BULK PATTERNS ===")

base_count = 0
bulk_count = 0

for row in rows:

    gt = row["gt_item_code"].strip()

    if not gt:
        continue

    item = matcher.item_lookup[
        row["tenant"]
    ].get(gt)

    if not item:
        continue

    if is_bulk(item):
        bulk_count += 1
    else:
        base_count += 1

print(f"positive GT base items : {base_count}")
print(f"positive GT bulk items : {bulk_count}")


print()
print("=== BULK GT WITHOUT 'BULK' IN SOURCE ===")

cases = []

for row in rows:

    gt = row["gt_item_code"].strip()

    if not gt:
        continue

    item = matcher.item_lookup[
        row["tenant"]
    ].get(gt)

    if not item or not is_bulk(item):
        continue

    query = normalize_text(
        row["raw_text"]
    )

    if "bulk" not in query.split():

        cases.append(
            (
                row["line_id"],
                row["raw_text"],
                gt,
                item["item_name"],
                row["qty"],
                row["uom_text"],
                row["unit_price"],
            )
        )


print(f"count: {len(cases)}")

for (
    line_id,
    raw_text,
    gt,
    item_name,
    qty,
    uom,
    price,
) in cases:

    print()
    print("-" * 80)
    print(f"line_id   : {line_id}")
    print(f"raw_text  : {raw_text}")
    print(f"GT        : {gt}")
    print(f"GT name   : {item_name}")
    print(f"qty       : {qty}")
    print(f"uom       : {uom}")
    print(f"unit_price: {price}")


print()
print("=== BASE GT WHEN BULK TWIN EXISTS ===")

cases = []

for row in rows:

    gt = row["gt_item_code"].strip()

    if not gt:
        continue

    gt_item = matcher.item_lookup[
        row["tenant"]
    ].get(gt)

    if not gt_item or is_bulk(gt_item):
        continue

    gt_name = normalize_text(
        gt_item["item_name"]
    )

    for candidate in matcher.active_catalogues[
        row["tenant"]
    ]:

        if not is_bulk(candidate):
            continue

        bulk_name = normalize_text(
            candidate["item_name"]
        )

        # Remove "bulk" so we can detect
        # catalogue base/bulk twins.
        bulk_without_marker = re.sub(
            r"\s*\(\s*bulk\s*\)\s*",
            " ",
            bulk_name,
        )

        bulk_without_marker = re.sub(
            r"\s+",
            " ",
            bulk_without_marker,
        ).strip()

        if bulk_without_marker == gt_name:

            cases.append(
                (
                    row["line_id"],
                    row["raw_text"],
                    gt_item["item_code"],
                    gt_item["item_name"],
                    candidate["item_code"],
                    candidate["item_name"],
                    row["qty"],
                    row["uom_text"],
                )
            )

            break


print(f"count: {len(cases)}")

for (
    line_id,
    raw_text,
    base_code,
    base_name,
    bulk_code,
    bulk_name,
    qty,
    uom,
) in cases:

    print()
    print("-" * 80)
    print(f"line_id   : {line_id}")
    print(f"raw_text  : {raw_text}")
    print(f"BASE GT   : {base_code}")
    print(f"BASE name : {base_name}")
    print(f"BULK twin : {bulk_code}")
    print(f"BULK name : {bulk_name}")
    print(f"qty       : {qty}")
    print(f"uom       : {uom}")