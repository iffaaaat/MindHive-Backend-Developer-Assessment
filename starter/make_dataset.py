#!/usr/bin/env python3
"""Deterministic generator for the backend assessment dataset.

Stdlib only. Re-running with the same seed reproduces byte-identical CSVs.

    python3 make_dataset.py --out ../data --seed 20260809

Emits:
    catalogue_acme.csv          tenant A catalogue (industrial hardware)
    catalogue_nordic.csv        tenant B catalogue (frozen food distribution)
    customer_sku_map.csv        buyer SKU -> item_code aliases (dirty on purpose)
    order_lines_train.csv       labelled order lines (candidate-visible)
    order_lines_holdout.csv     unlabelled order lines (candidate submits predictions)
    holdout_labels.csv          GRADERS ONLY - do not ship to candidate
    uom_reference.csv           pack/uom conversion reference
"""

import argparse
import csv
import json
import os
import random
import unicodedata

# --------------------------------------------------------------------------
# vocabularies
# --------------------------------------------------------------------------

HW_BRANDS = ["Remax", "Tolsen", "Kanto", "Hitex", "Vermont", "Stallion", "Bosco"]
HW_FAMILIES = [
    # (family name, unit, size axis, sizes, extra axis, extras)
    ("Hex Bolt", "Pcs", "size", ["M6x30", "M6x50", "M8x30", "M8x50", "M8x75", "M10x50", "M10x75", "M12x60"],
     "finish", ["Zinc Plated", "Stainless 304", "Stainless 316", "HDG"]),
    ("Self Drilling Screw", "Packet", "size", ["#8 x 3/4\"", "#8 x 1\"", "#10 x 1\"", "#10 x 1-1/2\"", "#12 x 2\""],
     "finish", ["Zinc Plated", "Stainless 410"]),
    ("Cable Tie", "Packet", "size", ["100mm", "150mm", "200mm", "300mm", "370mm", "450mm"],
     "colour", ["Black", "White", "Natural"]),
    ("PVC Pipe", "Length", "size", ["15mm", "20mm", "25mm", "32mm", "40mm", "50mm"],
     "grade", ["Class C", "Class D", "Class E"]),
    ("Ball Valve", "Nos", "size", ["1/2\"", "3/4\"", "1\"", "1-1/4\"", "2\""],
     "material", ["Brass", "PVC", "SS304"]),
    ("Angle Grinder Disc", "Packet", "size", ["4\"", "4.5\"", "5\"", "7\""],
     "grade", ["Cutting", "Grinding", "Flap"]),
    ("GI Wire", "Kg", "size", ["#14", "#16", "#18", "#20"], "grade", ["Soft", "Hard Drawn"]),
    ("Safety Helmet", "Nos", "colour", ["White", "Yellow", "Blue", "Red"], "grade", ["Standard", "Ratchet"]),
    ("Nitrile Glove", "Box", "size", ["S", "M", "L", "XL"], "colour", ["Blue", "Black"]),
    ("Masking Tape", "Roll", "size", ["12mm", "18mm", "24mm", "48mm"], "grade", ["General", "High Temp"]),
    ("Hose Clip", "Pcs", "size", ["13-19mm", "19-25mm", "25-38mm", "38-50mm"], "material", ["SS304", "Zinc"]),
    ("Wall Plug", "Packet", "size", ["6mm", "8mm", "10mm", "12mm"], "colour", ["Red", "Brown", "Blue"]),
]

FOOD_BRANDS = ["Fjordal", "Nordvik", "Cape Bay", "Golden Pantry", "Sisu", "Halberg"]
FOOD_FAMILIES = [
    ("Chicken Breast", "Kg", "cut", ["Whole", "Diced", "Strips"], "pack", ["1kg", "2kg", "5kg", "10kg"]),
    ("Beef Patty", "Packet", "cut", ["100g", "150g", "200g"], "pack", ["12s", "24s", "48s"]),
    ("Salmon Fillet", "Kg", "cut", ["Portion", "Side", "Trim D"], "pack", ["1kg", "3kg", "5kg"]),
    ("Potato Fries", "Packet", "cut", ["7mm", "10mm", "Crinkle", "Wedge"], "pack", ["1kg", "2.5kg"]),
    ("Mozzarella", "Kg", "cut", ["Block", "Shredded", "Diced"], "pack", ["1kg", "2kg"]),
    ("Full Cream Milk", "Nos", "cut", ["UHT", "Fresh"], "pack", ["200ml", "1L", "2L"]),
    ("Whipping Cream", "Nos", "cut", ["35%", "38%"], "pack", ["1L"]),
    ("Prawn", "Kg", "cut", ["16/20", "21/25", "31/40", "PDTO"], "pack", ["1kg", "2kg"]),
    ("Puff Pastry", "Packet", "cut", ["Sheet", "Block"], "pack", ["1kg", "2kg", "5kg"]),
    ("Vanilla Ice Cream", "Nos", "cut", ["Tub", "Cone"], "pack", ["1L", "4L", "6s"]),
    ("Butter Unsalted", "Packet", "cut", ["Block", "Sheet"], "pack", ["250g", "500g", "5kg"]),
    ("Squid Ring", "Kg", "cut", ["Breaded", "Raw"], "pack", ["1kg", "2kg"]),
]

MALAY = {
    "screw": "skru", "wire": "dawai", "pipe": "paip", "glove": "sarung tangan",
    "helmet": "topi keledar", "tape": "pita", "chicken": "ayam", "beef": "daging",
    "milk": "susu", "prawn": "udang", "butter": "mentega", "frozen": "beku",
    "white": "putih", "black": "hitam", "red": "merah", "blue": "biru",
}

ABBREV = [
    ("Stainless 304", "SS304"), ("Stainless 316", "SS316"), ("Stainless", "S/S"),
    ("Zinc Plated", "ZP"), ("Galvanised", "GALV"), ("Hex Bolt", "HEX BLT"),
    ("Self Drilling Screw", "SDS"), ("Angle Grinder Disc", "GRINDING DISC"),
    ("Full Cream Milk", "FC MILK"), ("Chicken Breast", "CHK BRST"),
    ("Unsalted", "UNSLT"), ("Packet", "PKT"), ("Length", "LGT"),
]

CHANNELS = ["whatsapp", "email_pdf", "portal_csv", "voice_note"]

PACK_WORDS = ["ctn", "carton", "box", "case", "pkt", "bag", "dozen", "doz"]


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(c for c in s.upper() if c.isalnum())


# --------------------------------------------------------------------------
# catalogue construction
# --------------------------------------------------------------------------

CAT_FIELDS = [
    "item_code", "item_name", "description", "brand", "item_group", "stock_uom",
    "uom_conversions", "barcode", "manufacturer_part_no", "disabled",
    "available_qty", "list_price",
]


def build_catalogue(rng, families, brands, prefix, group_root, n_target):
    combos = []
    for fam, uom, _ax1, vals1, ax2, vals2 in families:
        for brand in brands:
            for v1 in vals1:
                for v2 in vals2:
                    combos.append((fam, uom, ax2, v1, v2, brand))
    rng.shuffle(combos)
    combos = combos[:n_target]

    rows = []
    seq = 0
    for fam, uom, ax2, v1, v2, brand in combos:
        name = f"{brand} {fam} {v1} {v2}".replace("  ", " ")
        seq += 1
        code = f"{prefix}-{slug(fam)[:4]}{seq:04d}"
        packs = [{"uom": uom, "conversion_factor": 1.0}]
        if uom in ("Pcs", "Packet", "Nos", "Roll"):
            inner = rng.choice([6, 10, 12, 24, 50, 100])
            packs.append({"uom": "Carton", "conversion_factor": float(inner)})
        desc = f"{fam} {v1}, {ax2}: {v2}. Brand {brand}. Sold per {uom}."
        rows.append({
            "item_code": code,
            "item_name": name,
            "description": desc,
            "brand": brand,
            "item_group": f"{group_root} > {fam}",
            "stock_uom": uom,
            "uom_conversions": json.dumps(packs, separators=(",", ":")),
            "barcode": "" if rng.random() < 0.45 else f"9{rng.randrange(10**11):011d}",
            "manufacturer_part_no": "" if rng.random() < 0.6 else f"{slug(brand)[:3]}{rng.randrange(10**6):06d}",
            "disabled": 0,
            "available_qty": rng.choice([0, 0, 3, 12, 40, 150, 900]),
            "list_price": round(rng.uniform(0.8, 480), 2),
        })

    # --- deliberate catalogue pathologies -------------------------------
    # 1. near-duplicate pairs: same visible name, one active one disabled (obsolete)
    for r in rng.sample(rows, k=max(6, n_target // 60)):
        seq += 1
        dup = dict(r)
        dup["item_code"] = r["item_code"] + "-OLD"
        dup["disabled"] = 1
        dup["available_qty"] = 0
        dup["description"] = r["description"] + " (superseded)"
        rows.append(dup)
    # 2. active twins: same name, two live codes, different pack size
    for r in rng.sample(rows[:n_target], k=max(4, n_target // 90)):
        seq += 1
        twin = dict(r)
        twin["item_code"] = f"{r['item_code']}B"
        twin["item_name"] = r["item_name"] + " (Bulk)"
        twin["uom_conversions"] = json.dumps(
            [{"uom": r["stock_uom"], "conversion_factor": 1.0},
             {"uom": "Carton", "conversion_factor": 144.0}], separators=(",", ":"))
        rows.append(twin)
    # 3. placeholder / junk rows real catalogues carry
    for i in range(max(3, n_target // 120)):
        rows.append({
            "item_code": f"{prefix}-MISC{i:03d}",
            "item_name": rng.choice(["MISC CHARGE", "DELIVERY FEE", "SAMPLE - DO NOT SELL", "OPENING BALANCE"]),
            "description": "", "brand": "", "item_group": f"{group_root} > Misc",
            "stock_uom": "Nos", "uom_conversions": json.dumps([{"uom": "Nos", "conversion_factor": 1.0}]),
            "barcode": "", "manufacturer_part_no": "", "disabled": 0,
            "available_qty": 0, "list_price": 0.0,
        })
    rng.shuffle(rows)
    return rows


# --------------------------------------------------------------------------
# noise operators applied to a catalogue name to make a raw order line
# --------------------------------------------------------------------------

def op_typo(rng, s):
    if len(s) < 6:
        return s
    i = rng.randrange(1, len(s) - 1)
    mode = rng.choice(["swap", "drop", "double"])
    if mode == "swap":
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if mode == "drop":
        return s[:i] + s[i + 1:]
    return s[:i] + s[i] + s[i:]


def op_case(rng, s):
    return rng.choice([s.upper(), s.lower(), s.title()])


def op_abbrev(rng, s):
    for long, short in ABBREV:
        if long.lower() in s.lower():
            i = s.lower().index(long.lower())
            return s[:i] + short + s[i + len(long):]
    return s


def op_malay(rng, s):
    out = s
    for en, ms in MALAY.items():
        if en in out.lower():
            i = out.lower().index(en)
            out = out[:i] + ms + out[i + len(en):]
            break
    return out


def op_drop_tokens(rng, s):
    toks = s.split()
    if len(toks) <= 3:
        return s
    keep = [t for t in toks if rng.random() > 0.28]
    return " ".join(keep) if keep else s


def op_pack_suffix(rng, s):
    return f"{s} x{rng.choice([6, 12, 24, 48])}{rng.choice(['', ' ' + rng.choice(PACK_WORDS)])}"


def op_noise_prefix(rng, s):
    return rng.choice(["pls send ", "need ", "item: ", "1) ", "- ", "urgent ", ""]) + s


def op_punct(rng, s):
    return s.replace(" ", rng.choice(["  ", " - ", "/", " "])).replace('"', rng.choice(['"', "''", " inch"]))


NOISE_OPS = [op_typo, op_case, op_abbrev, op_malay, op_drop_tokens, op_pack_suffix, op_noise_prefix, op_punct]


# --------------------------------------------------------------------------
# order line generation
# --------------------------------------------------------------------------

LINE_FIELDS = [
    "line_id", "tenant", "customer_id", "channel", "order_date", "raw_text",
    "qty", "uom_text", "unit_price", "buyer_sku", "raw_barcode", "notes",
]
LABEL_FIELDS = ["line_id", "gt_item_code", "gt_class"]

CLASSES = [
    "clean",            # near-verbatim catalogue name
    "typo",             # spelling damage
    "abbrev",           # trade abbreviation
    "bilingual",        # Malay/English mix
    "sparse",           # tokens dropped, underspecified but still unique
    "pack_confusion",   # pack/uom mismatch with stock uom
    "buyer_sku",        # resolvable only via customer_sku_map
    "barcode",          # resolvable via barcode
    "stale_alias",      # buyer sku maps to a superseded/disabled code
    "ambiguous",        # matches 2+ live items equally -> must abstain
    "absent",           # not in catalogue at all -> must abstain
    "junk",             # not an item line at all -> must abstain
]

CLASS_MIX = (
    ["clean"] * 7 + ["typo"] * 10 + ["abbrev"] * 9 + ["bilingual"] * 7 +
    ["sparse"] * 8 + ["pack_confusion"] * 8 + ["buyer_sku"] * 10 + ["barcode"] * 6 +
    ["stale_alias"] * 9 + ["ambiguous"] * 8 + ["absent"] * 8 + ["junk"] * 5
)

JUNK_TEXTS = [
    "thanks bro", "deliver by friday please", "same as last month order",
    "PO attached", "subtotal", "delivery charge", "pls confirm stock first",
    "kindly quote best price", "ATTN: purchasing dept", "----",
]

ABSENT_TEMPLATES = [
    "Makita LS1040 mitre saw 240v", "Duracell AA battery 8 pack",
    "3M 8210 N95 respirator box 20", "Cadbury Dairy Milk 165g",
    "Epson 003 ink black bottle", "Nescafe Gold refill 170g",
    "Copper pipe 22mm x 3m Class 2", "Wagyu striploin MB7 grain fed",
]


def make_lines(rng, tenant, catalogue, alias_rows, start_id, n, prefix):
    by_code = {r["item_code"]: r for r in catalogue}
    live = [r for r in catalogue if not int(r["disabled"]) and r["item_name"] not in ("MISC CHARGE",)]
    live = [r for r in live if r["brand"]]
    # name -> codes, to find genuinely ambiguous surfaces
    twins = {}
    for r in live:
        key = r["item_name"].replace(" (Bulk)", "")
        twins.setdefault(key, []).append(r["item_code"])
    ambiguous_keys = [k for k, v in twins.items() if len(v) > 1]
    superseded = [r for r in live if r["item_code"] + "-OLD" in by_code]

    alias_by_code = {}
    for a in alias_rows:
        if a["tenant"] == tenant:
            alias_by_code.setdefault(a["item_code"], []).append(a)

    lines, labels, extra_aliases = [], [], []
    for i in range(n):
        cls = CLASS_MIX[(i * 7 + 3) % len(CLASS_MIX)]
        lid = f"{prefix}-{start_id + i:04d}"
        cust = f"CUST-{rng.randrange(1, 9):03d}"
        row = {
            "line_id": lid, "tenant": tenant, "customer_id": cust,
            "channel": rng.choice(CHANNELS),
            "order_date": f"2026-0{rng.randrange(4, 9)}-{rng.randrange(1, 29):02d}",
            "raw_text": "", "qty": rng.choice([1, 2, 3, 5, 6, 10, 12, 20, 24, 50, 100]),
            "uom_text": "", "unit_price": "", "buyer_sku": "", "raw_barcode": "", "notes": "",
        }
        gt = ""

        if cls == "junk":
            row["raw_text"] = rng.choice(JUNK_TEXTS)
            row["qty"] = rng.choice(["", 1])
        elif cls == "absent":
            row["raw_text"] = rng.choice(ABSENT_TEMPLATES)
            row["uom_text"] = rng.choice(["pcs", "unit", "box", ""])
        elif cls == "ambiguous":
            if ambiguous_keys:
                key = rng.choice(ambiguous_keys)
                row["raw_text"] = op_drop_tokens(rng, key)
            else:
                row["raw_text"] = rng.choice(live)["brand"]
            row["uom_text"] = rng.choice(["pcs", "ctn", ""])
        else:
            if cls == "stale_alias" and superseded:
                item = rng.choice(superseded)
            else:
                item = rng.choice(live)
            gt = item["item_code"]
            base = item["item_name"]
            if cls == "clean":
                text = base
            elif cls == "typo":
                text = op_typo(rng, op_typo(rng, base))
            elif cls == "abbrev":
                text = op_abbrev(rng, op_case(rng, base))
            elif cls == "bilingual":
                text = op_malay(rng, base)
                if rng.random() < 0.5:
                    text = op_malay(rng, text)
            elif cls == "sparse":
                text = op_drop_tokens(rng, base)
                # keep it resolvable: re-append the size token if we lost everything distinctive
                if len(text.split()) < 3:
                    text = " ".join(base.split()[:2] + base.split()[-2:])
            elif cls == "pack_confusion":
                text = op_pack_suffix(rng, base)
                row["uom_text"] = rng.choice(["ctn", "carton", "box", "case"])
                convs = json.loads(item["uom_conversions"])
                cf = max(c["conversion_factor"] for c in convs)
                row["unit_price"] = round(float(item["list_price"]) * cf, 2)
                row["notes"] = "price quoted per outer"
            elif cls == "buyer_sku":
                aliases = alias_by_code.get(item["item_code"], [])
                if not aliases:
                    text = base
                    cls = "clean"
                else:
                    a = rng.choice(aliases)
                    row["buyer_sku"] = a["customer_sku"]
                    row["customer_id"] = a["customer_id"]
                    text = rng.choice([a["customer_description"], op_drop_tokens(rng, base)])
            elif cls == "barcode":
                if item["barcode"]:
                    row["raw_barcode"] = item["barcode"]
                    text = op_drop_tokens(rng, base)
                else:
                    text = base
                    cls = "clean"
            elif cls == "stale_alias":
                old = item["item_code"] + "-OLD"
                if old in by_code:
                    sku = f"{cust.split('-')[1]}{rng.randrange(10**6):06d}"
                    row["buyer_sku"] = sku
                    # the alias points at the SUPERSEDED code; ground truth is the
                    # live successor, so blindly trusting the alias table is wrong
                    extra_aliases.append({
                        "tenant": tenant, "customer_id": cust, "customer_sku": sku,
                        "item_code": old,
                        "customer_description": op_drop_tokens(rng, item["item_name"]),
                        "valid_from": "2026-01-01", "valid_to": "", "source": "manual_import",
                        "confidence": 1.0,
                    })
                    text = op_drop_tokens(rng, base)
                else:
                    text = base
                    cls = "clean"
            else:
                text = base

            if rng.random() < 0.35:
                text = op_noise_prefix(rng, text)
            if rng.random() < 0.25:
                text = op_punct(rng, text)
            row["raw_text"] = text
            if not row["uom_text"] and rng.random() < 0.6:
                row["uom_text"] = rng.choice([item["stock_uom"].lower(), "pcs", "unit", "ea", ""])
            if not row["unit_price"] and rng.random() < 0.5:
                row["unit_price"] = round(float(item["list_price"]) * rng.uniform(0.85, 1.15), 2)

        lines.append(row)
        labels.append({"line_id": lid, "gt_item_code": gt, "gt_class": cls})

    # Label hygiene: a token-dropped line that still matches several live items
    # is not "sparse but resolvable" - it is genuinely ambiguous. Relabel it so
    # the answer key never punishes a correct abstention.
    def toks(s):
        return {t for t in "".join(c if c.isalnum() else " " for c in s.lower()).split() if len(t) > 1}

    live_toks = [(r["item_code"], toks(r["item_name"])) for r in live]
    for row, lab in zip(lines, labels):
        if lab["gt_class"] not in ("sparse", "clean"):
            continue
        if row["buyer_sku"] or row["raw_barcode"]:
            continue
        t = toks(row["raw_text"])
        hits = {code for code, ct in live_toks if t and t <= ct}
        if len(hits) > 1:
            lab["gt_item_code"] = ""
            lab["gt_class"] = "ambiguous"
    return lines, labels, extra_aliases


# --------------------------------------------------------------------------
# customer sku aliases (deliberately dirty)
# --------------------------------------------------------------------------

ALIAS_FIELDS = ["tenant", "customer_id", "customer_sku", "item_code",
                "customer_description", "valid_from", "valid_to", "source", "confidence"]


def build_aliases(rng, tenant, catalogue, n):
    live = [r for r in catalogue if not int(r["disabled"]) and r["brand"]]
    rows = []
    for i in range(n):
        item = rng.choice(live)
        cust = f"CUST-{rng.randrange(1, 9):03d}"
        sku = f"{cust.split('-')[1]}{rng.randrange(10**6):06d}"
        rows.append({
            "tenant": tenant, "customer_id": cust, "customer_sku": sku,
            "item_code": item["item_code"],
            "customer_description": op_drop_tokens(rng, op_case(rng, item["item_name"])),
            "valid_from": "2026-01-01", "valid_to": "",
            "source": rng.choice(["confirmed_order", "confirmed_order", "manual_import", "inferred_match"]),
            "confidence": rng.choice([1.0, 1.0, 0.72, 0.55]),
        })
    # collisions: same customer_sku pointing at two different codes (one expired)
    for r in rng.sample(rows, k=max(4, n // 25)):
        bad = dict(r)
        bad["item_code"] = rng.choice(live)["item_code"]
        bad["valid_to"] = "2026-03-31"
        bad["source"] = "manual_import"
        rows.append(bad)
    # cross-tenant lookalikes: a buyer sku that equals another tenant's item_code
    for r in rng.sample(rows, k=max(3, n // 40)):
        r["customer_sku"] = rng.choice(live)["item_code"].replace(r["tenant"][:3].upper(), "NRD")
    return rows


# --------------------------------------------------------------------------

def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {path} ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../data")
    ap.add_argument("--seed", type=int, default=20260809)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)

    acme = build_catalogue(rng, HW_FAMILIES, HW_BRANDS, "ACM", "All Items > Hardware", 1400)
    nordic = build_catalogue(rng, FOOD_FAMILIES, FOOD_BRANDS, "NRD", "All Items > Frozen", 900)
    write_csv(os.path.join(args.out, "catalogue_acme.csv"), CAT_FIELDS, acme)
    write_csv(os.path.join(args.out, "catalogue_nordic.csv"), CAT_FIELDS, nordic)

    aliases = build_aliases(rng, "acme", acme, 420) + build_aliases(rng, "nordic", nordic, 260)

    tr_a, la_a, xa1 = make_lines(rng, "acme", acme, aliases, 1, 260, "ACM-T")
    tr_n, la_n, xa2 = make_lines(rng, "nordic", nordic, aliases, 1, 160, "NRD-T")
    train = tr_a + tr_n
    train_lab = la_a + la_n
    for r, l in zip(train, train_lab):
        r["gt_item_code"] = l["gt_item_code"]
    write_csv(os.path.join(args.out, "order_lines_train.csv"),
              LINE_FIELDS + ["gt_item_code"], train)

    ho_a, hl_a, xa3 = make_lines(rng, "acme", acme, aliases, 5001, 190, "ACM-H")
    ho_n, hl_n, xa4 = make_lines(rng, "nordic", nordic, aliases, 5001, 110, "NRD-H")
    holdout = ho_a + ho_n
    aliases += xa1 + xa2 + xa3 + xa4
    rng.shuffle(aliases)
    write_csv(os.path.join(args.out, "customer_sku_map.csv"), ALIAS_FIELDS, aliases)
    write_csv(os.path.join(args.out, "order_lines_holdout.csv"), LINE_FIELDS, holdout)
    write_csv(os.path.join(args.out, "holdout_labels.GRADERS-ONLY.csv"),
              LABEL_FIELDS, hl_a + hl_n)

    uom_rows = []
    for name, tag in (("acme", acme), ("nordic", nordic)):
        for r in tag:
            for c in json.loads(r["uom_conversions"]):
                uom_rows.append({"tenant": name, "item_code": r["item_code"],
                                 "uom": c["uom"], "conversion_factor": c["conversion_factor"],
                                 "is_stock_uom": int(c["uom"] == r["stock_uom"])})
    write_csv(os.path.join(args.out, "uom_reference.csv"),
              ["tenant", "item_code", "uom", "conversion_factor", "is_stock_uom"], uom_rows)


if __name__ == "__main__":
    main()
