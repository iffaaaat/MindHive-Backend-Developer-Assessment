from statistics import median

from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()


price_rows = []
correct_top1_rows = []
wrong_top1_rows = []


for line in rows:

    gt = line["gt_item_code"].strip()
    raw_price = line["unit_price"].strip()

    # We only evaluate rows where:
    # 1. ground truth exists
    # 2. order price exists
    if not gt or not raw_price:
        continue

    try:
        order_price = float(raw_price)
    except ValueError:
        continue

    candidates = matcher.rank_candidates(
        line,
        limit=5,
        retrieval_limit=30,
    )

    if not candidates:
        continue

    # Find the ground-truth catalogue item.
    gt_item = None

    for item in matcher.active_catalogues[line["tenant"]]:
        if item["item_code"] == gt:
            gt_item = item
            break

    if gt_item is None:
        continue

    try:
        catalogue_price = float(gt_item["list_price"])
    except (ValueError, TypeError):
        continue

    if catalogue_price <= 0:
        continue

    # Relative difference:
    #
    # order=100, catalogue=100 -> 0.00
    # order=110, catalogue=100 -> 0.10
    # order=150, catalogue=100 -> 0.50
    relative_difference = abs(
        order_price - catalogue_price
    ) / catalogue_price

    record = {
        "line": line,
        "gt_item": gt_item,
        "order_price": order_price,
        "catalogue_price": catalogue_price,
        "difference": relative_difference,
        "top1": candidates[0],
        "candidates": candidates,
    }

    price_rows.append(record)

    if candidates[0]["item"]["item_code"] == gt:
        correct_top1_rows.append(record)
    else:
        wrong_top1_rows.append(record)


print("=== PRICE SIGNAL ===")
print("usable labelled price rows:", len(price_rows))

if price_rows:
    differences = [
        r["difference"]
        for r in price_rows
    ]

    print(
        "median GT relative price difference:",
        round(median(differences), 4),
    )

    print(
        "within 10%:",
        sum(d <= 0.10 for d in differences),
        "/",
        len(differences),
    )

    print(
        "within 25%:",
        sum(d <= 0.25 for d in differences),
        "/",
        len(differences),
    )

    print(
        "within 50%:",
        sum(d <= 0.50 for d in differences),
        "/",
        len(differences),
    )


print()
print("=== PRICE BY CURRENT TOP-1 RESULT ===")

for label, group in [
    ("correct top1", correct_top1_rows),
    ("wrong top1", wrong_top1_rows),
]:

    if not group:
        continue

    differences = [
        r["difference"]
        for r in group
    ]

    print()
    print(label)
    print("rows:", len(group))
    print(
        "median GT price difference:",
        round(median(differences), 4),
    )


print()
print("=== WRONG TOP-1 CASES WHERE PRICE MAY HELP ===")

shown = 0

for record in wrong_top1_rows:

    line = record["line"]
    gt = line["gt_item_code"]
    order_price = record["order_price"]

    candidates = record["candidates"]

    gt_candidate = None

    for candidate in candidates:
        if candidate["item"]["item_code"] == gt:
            gt_candidate = candidate
            break

    # Only investigate cases where retrieval succeeded.
    if gt_candidate is None:
        continue

    top1 = candidates[0]

    try:
        top1_price = float(
            top1["item"]["list_price"]
        )
        gt_price = float(
            gt_candidate["item"]["list_price"]
        )
    except (ValueError, TypeError):
        continue

    if top1_price <= 0 or gt_price <= 0:
        continue

    top1_diff = abs(
        order_price - top1_price
    ) / top1_price

    gt_diff = abs(
        order_price - gt_price
    ) / gt_price

    # Show examples where GT is substantially
    # closer in price than the current prediction.
    if gt_diff + 0.10 < top1_diff:

        print("=" * 80)
        print("line:", line["line_id"])
        print("text:", line["raw_text"])
        print("order price:", order_price)

        print()
        print("CURRENT TOP1")
        print(
            top1["item"]["item_code"],
            top1["item"]["item_name"],
        )
        print("catalogue price:", top1_price)
        print(
            "relative difference:",
            round(top1_diff, 4),
        )
        print(
            "matcher score:",
            round(top1["score"], 4),
        )

        print()
        print("GROUND TRUTH")
        print(
            gt_candidate["item"]["item_code"],
            gt_candidate["item"]["item_name"],
        )
        print("catalogue price:", gt_price)
        print(
            "relative difference:",
            round(gt_diff, 4),
        )
        print(
            "matcher score:",
            round(gt_candidate["score"], 4),
        )

        shown += 1

        if shown >= 15:
            break


print()
print("examples shown:", shown)