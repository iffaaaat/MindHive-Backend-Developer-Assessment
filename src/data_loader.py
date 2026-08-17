import csv
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_csv(filename):
    path = DATA_DIR / filename

    with path.open(
        mode="r",
        encoding="utf-8",
        newline=""
    ) as file:
        return list(csv.DictReader(file))


def load_catalogues():
    return {
        "acme": load_csv("catalogue_acme.csv"),
        "nordic": load_csv("catalogue_nordic.csv"),
    }


def load_customer_sku_map():
    return load_csv("customer_sku_map.csv")


def load_uom_reference():
    return load_csv("uom_reference.csv")


def load_training_lines():
    return load_csv("order_lines_train.csv")

def load_holdout_lines():
    return load_csv("order_lines_holdout.csv")