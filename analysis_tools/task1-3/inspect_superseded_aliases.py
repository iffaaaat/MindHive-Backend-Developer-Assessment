from collections import Counter

from src.data_loader import (
    load_catalogues,
    load_customer_sku_map,
    load_training_lines,
)


catalogues = load_catalogues()
aliases = load_customer_sku_map()
train = load_training_lines()


# --------------------------------------------------
# Full catalogue lookup, including disabled items
# --------------------------------------------------

catalogue_lookup = {}

for tenant, items in catalogues.items():
    catalogue_lookup[tenant] = {
        item["item_code"]: item
        for item in items
    }


# --------------------------------------------------
# Find alias mappings that target disabled items
# --------------------------------------------------

disabled_aliases = []

for alias in aliases:

    tenant = alias["tenant"]
    target_code = alias["item_code"]

    item = catalogue_lookup.get(
        tenant,
        {},
    ).get(target_code)

    if not item:
        continue

    if item["disabled"] != "1":
        continue

    base_code = target_code

    if base_code.endswith("-OLD"):
        base_code = base_code[:-4]

    successor = catalogue_lookup[
        tenant
    ].get(base_code)

    disabled_aliases.append(
        {
            "alias": alias,
            "old_item": item,
            "base_code": base_code,
            "successor": successor,
        }
    )


print("=== DISABLED ALIAS TARGETS ===")
print(
    "aliases pointing to disabled items:",
    len(disabled_aliases),
)


with_active_successor = [
    row
    for row in disabled_aliases
    if (
        row["successor"]
        and row["successor"]["disabled"] == "0"
    )
]

print(
    "with active same-base successor:",
    len(with_active_successor),
)


# --------------------------------------------------
# Compare old vs successor names
# --------------------------------------------------

print()
print("=== FIRST 20 SUCCESSOR PAIRS ===")

for row in with_active_successor[:20]:

    alias = row["alias"]
    old_item = row["old_item"]
    successor = row["successor"]

    print()
    print(
        alias["tenant"],
        alias["customer_id"],
        alias["customer_sku"],
    )

    print(
        " OLD:",
        old_item["item_code"],
        "|",
        old_item["item_name"],
    )

    print(
        " NEW:",
        successor["item_code"],
        "|",
        successor["item_name"],
    )

    print(
        " source:",
        alias["source"],
        "confidence:",
        alias["confidence"],
    )


# --------------------------------------------------
# Training rows that use those aliases
# --------------------------------------------------

training_hits = []

for line in train:

    buyer_sku = line["buyer_sku"].strip()

    if not buyer_sku:
        continue

    for row in disabled_aliases:

        alias = row["alias"]

        if (
            alias["tenant"] == line["tenant"]
            and alias["customer_id"] == line["customer_id"]
            and alias["customer_sku"] == buyer_sku
        ):

            training_hits.append(
                {
                    "line": line,
                    **row,
                }
            )


print()
print("=== TRAINING ROWS USING DISABLED ALIASES ===")
print("rows:", len(training_hits))


successor_correct = 0
successor_wrong = 0
no_active_successor = 0


for row in training_hits:

    line = row["line"]
    successor = row["successor"]

    predicted = None

    if (
        successor
        and successor["disabled"] == "0"
    ):
        predicted = successor["item_code"]

    if predicted is None:
        no_active_successor += 1

    elif predicted == line["gt_item_code"]:
        successor_correct += 1

    else:
        successor_wrong += 1


print(
    "active successor matches GT:",
    successor_correct,
)

print(
    "active successor wrong:",
    successor_wrong,
)

print(
    "no active successor:",
    no_active_successor,
)


# --------------------------------------------------
# Print any wrong cases
# --------------------------------------------------

print()
print("=== WRONG SUCCESSOR CASES ===")

wrong_cases = 0

for row in training_hits:

    line = row["line"]
    successor = row["successor"]

    if not successor:
        continue

    if successor["disabled"] == "1":
        continue

    if successor["item_code"] == line["gt_item_code"]:
        continue

    wrong_cases += 1

    print()
    print("line:", line["line_id"])
    print("text:", line["raw_text"])
    print("buyer_sku:", line["buyer_sku"])
    print("GT:", line["gt_item_code"])

    print(
        "old:",
        row["old_item"]["item_code"],
        row["old_item"]["item_name"],
    )

    print(
        "successor:",
        successor["item_code"],
        successor["item_name"],
    )


print()
print("wrong successor cases:", wrong_cases)