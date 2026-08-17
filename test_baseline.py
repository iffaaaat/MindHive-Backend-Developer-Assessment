from src.data_loader import load_training_lines
from src.matcher import Matcher


matcher = Matcher()
rows = load_training_lines()

total_rows = len(rows)

resolved = 0
correct = 0
wrong = 0

barcode_used = 0
alias_used = 0
both_agree = 0
both_disagree = 0


for line in rows:
    barcode_match = matcher.resolve_barcode(line)
    alias_match = matcher.resolve_alias(line)

    prediction = None
    source = None

    if barcode_match and alias_match:
        if barcode_match["item_code"] == alias_match["item_code"]:
            both_agree += 1
            prediction = barcode_match["item_code"]
            source = "barcode+alias"
        else:
            both_disagree += 1
            # Contradictory strong evidence:
            # abstain rather than guessing.
            continue

    elif barcode_match:
        prediction = barcode_match["item_code"]
        source = "barcode"

    elif alias_match:
        prediction = alias_match["item_code"]
        source = "alias"

    if prediction is None:
        continue

    resolved += 1

    if source == "barcode":
        barcode_used += 1
    elif source == "alias":
        alias_used += 1

    if prediction == line["gt_item_code"]:
        correct += 1
    else:
        wrong += 1
        print(
            "WRONG:",
            line["line_id"],
            "source=", source,
            "pred=", prediction,
            "gt=", line["gt_item_code"],
        )


precision = correct / resolved if resolved else 0
coverage = resolved / total_rows if total_rows else 0


print("=== COMBINED STRONG SIGNAL BASELINE ===")
print("rows:", total_rows)
print("resolved:", resolved)
print("correct:", correct)
print("wrong:", wrong)
print("precision:", round(precision, 4))
print("coverage:", round(coverage, 4))
print("barcode-only used:", barcode_used)
print("alias-only used:", alias_used)
print("both agree:", both_agree)
print("both disagree:", both_disagree)