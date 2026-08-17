import csv
from collections import Counter, defaultdict
from datetime import datetime


def load_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


acme = load_csv("data/catalogue_acme.csv")
nordic = load_csv("data/catalogue_nordic.csv")
aliases = load_csv("data/customer_sku_map.csv")
train = load_csv("data/order_lines_train.csv")

catalogues = {
    "acme": acme,
    "nordic": nordic,
}


# --------------------------------------------------
# Catalogue health
# --------------------------------------------------

print("=== CATALOGUE HEALTH ===")

for tenant, rows in catalogues.items():
    disabled = [r for r in rows if r["disabled"] == "1"]
    zero_stock = [
        r for r in rows
        if r["disabled"] == "0"
        and float(r["available_qty"] or 0) == 0
    ]

    codes = Counter(r["item_code"] for r in rows)
    duplicate_codes = {
        code: count
        for code, count in codes.items()
        if count > 1
    }

    print(f"\n{tenant.upper()}")
    print("rows:", len(rows))
    print("disabled:", len(disabled))
    print("active zero-stock:", len(zero_stock))
    print("duplicate item codes:", len(duplicate_codes))


# --------------------------------------------------
# Alias health
# --------------------------------------------------

print("\n=== ALIAS HEALTH ===")

print("total aliases:", len(aliases))

sources = Counter(r["source"] for r in aliases)
print("sources:", sources)

low_confidence = [
    r for r in aliases
    if float(r["confidence"] or 0) < 1.0
]
print("confidence < 1.0:", len(low_confidence))

expired = [
    r for r in aliases
    if r["valid_to"].strip()
]
print("has valid_to:", len(expired))


# Same tenant/customer/SKU mapping to multiple item codes
mapping_groups = defaultdict(set)

for r in aliases:
    key = (
        r["tenant"],
        r["customer_id"],
        r["customer_sku"],
    )
    mapping_groups[key].add(r["item_code"])

conflicts = {
    key: values
    for key, values in mapping_groups.items()
    if len(values) > 1
}

print("conflicting alias keys:", len(conflicts))

for key, values in list(conflicts.items())[:10]:
    print("CONFLICT:", key, "->", sorted(values))


# --------------------------------------------------
# Cross-tenant-looking buyer SKUs
# --------------------------------------------------

acme_codes = {r["item_code"] for r in acme}
nordic_codes = {r["item_code"] for r in nordic}

suspicious_cross_tenant = []

for r in aliases:
    sku = r["customer_sku"]

    if r["tenant"] == "acme" and sku in nordic_codes:
        suspicious_cross_tenant.append(r)

    elif r["tenant"] == "nordic" and sku in acme_codes:
        suspicious_cross_tenant.append(r)

print(
    "buyer SKUs equal to another tenant's catalogue code:",
    len(suspicious_cross_tenant),
)

for r in suspicious_cross_tenant[:10]:
    print("CROSS-TENANT LOOKALIKE:", r)


# --------------------------------------------------
# Training-set signal availability
# --------------------------------------------------

print("\n=== TRAIN SIGNALS ===")

print("rows:", len(train))
print(
    "with buyer_sku:",
    sum(bool(r["buyer_sku"].strip()) for r in train),
)
print(
    "with barcode:",
    sum(bool(r["raw_barcode"].strip()) for r in train),
)
print(
    "with uom:",
    sum(bool(r["uom_text"].strip()) for r in train),
)
print(
    "with unit price:",
    sum(bool(r["unit_price"].strip()) for r in train),
)
print(
    "blank ground truth:",
    sum(not r["gt_item_code"].strip() for r in train),
)


# --------------------------------------------------
# Ground-truth sanity
# --------------------------------------------------

catalogue_codes = {
    "acme": {r["item_code"] for r in acme},
    "nordic": {r["item_code"] for r in nordic},
}

missing_gt = []

for r in train:
    gt = r["gt_item_code"].strip()

    if gt and gt not in catalogue_codes[r["tenant"]]:
        missing_gt.append(r)

print(
    "nonblank GT missing from tenant catalogue:",
    len(missing_gt),
)

for r in missing_gt[:10]:
    print("MISSING GT:", r["line_id"], r["tenant"], r["gt_item_code"])

print("\n=== STRONG SIGNAL QUALITY ===")

# Build catalogue lookup
catalogue_lookup = {}

for tenant, rows in catalogues.items():
    catalogue_lookup[tenant] = {
        r["item_code"]: r
        for r in rows
    }


# -------------------------
# Barcode quality
# -------------------------

barcode_lookup = {}

for tenant, rows in catalogues.items():
    barcode_lookup[tenant] = defaultdict(list)

    for item in rows:
        barcode = item["barcode"].strip()

        if barcode:
            barcode_lookup[tenant][barcode].append(item)


barcode_rows = [
    r for r in train
    if r["raw_barcode"].strip()
]

barcode_resolved = 0
barcode_correct = 0
barcode_wrong = 0
barcode_ambiguous = 0

for r in barcode_rows:
    matches = barcode_lookup[r["tenant"]].get(
        r["raw_barcode"].strip(),
        []
    )

    active_matches = [
        item for item in matches
        if item["disabled"] == "0"
    ]

    if len(active_matches) == 1:
        barcode_resolved += 1
        prediction = active_matches[0]["item_code"]

        if prediction == r["gt_item_code"]:
            barcode_correct += 1
        else:
            barcode_wrong += 1
            print(
                "BARCODE WRONG:",
                r["line_id"],
                r["raw_barcode"],
                "pred=", prediction,
                "gt=", r["gt_item_code"],
            )

    elif len(active_matches) > 1:
        barcode_ambiguous += 1


print("barcode lines:", len(barcode_rows))
print("uniquely resolved:", barcode_resolved)
print("correct:", barcode_correct)
print("wrong:", barcode_wrong)
print("ambiguous:", barcode_ambiguous)


# -------------------------
# Buyer SKU quality
# -------------------------

alias_lookup = defaultdict(list)

for alias in aliases:
    key = (
        alias["tenant"],
        alias["customer_id"],
        alias["customer_sku"],
    )
    alias_lookup[key].append(alias)


buyer_rows = [
    r for r in train
    if r["buyer_sku"].strip()
]

unique_alias = 0
correct_alias = 0
wrong_alias = 0
conflicting_alias = 0
unresolved_alias = 0

for r in buyer_rows:
    key = (
        r["tenant"],
        r["customer_id"],
        r["buyer_sku"],
    )

    matches = alias_lookup.get(key, [])

    # Keep mappings valid on order date
    valid = []

    for alias in matches:
        order_date = r["order_date"]

        if alias["valid_from"] and order_date < alias["valid_from"]:
            continue

        if alias["valid_to"] and order_date > alias["valid_to"]:
            continue

        item = catalogue_lookup[r["tenant"]].get(alias["item_code"])

        if not item:
            continue

        if item["disabled"] == "1":
            continue

        valid.append(alias)

    targets = {
        alias["item_code"]
        for alias in valid
    }

    if len(targets) == 1:
        unique_alias += 1
        prediction = next(iter(targets))

        if prediction == r["gt_item_code"]:
            correct_alias += 1
        else:
            wrong_alias += 1
            print(
                "ALIAS WRONG:",
                r["line_id"],
                r["buyer_sku"],
                "pred=", prediction,
                "gt=", r["gt_item_code"],
                "mappings=", valid,
            )

    elif len(targets) > 1:
        conflicting_alias += 1
        print(
            "ALIAS CONFLICT:",
            r["line_id"],
            r["buyer_sku"],
            targets,
            "gt=", r["gt_item_code"],
        )

    else:
        unresolved_alias += 1


print("\nbuyer SKU lines:", len(buyer_rows))
print("unique valid alias:", unique_alias)
print("correct:", correct_alias)
print("wrong:", wrong_alias)
print("conflicting:", conflicting_alias)
print("unresolved:", unresolved_alias)