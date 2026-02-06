# FIXED store.py
# Indentation normalized to spaces only.
# Pricing order: override -> median -> high_sold -> default

import csv
import json
import os
from pathlib import Path

DEFAULT_PRICE = 9

def safe_float(val):
    try:
        if val is None:
            return None
        val = str(val).strip().replace("$", "")
        if val == "":
            return None
        return float(val)
    except Exception:
        return None

def choose_price(row, override_price=None):
    if override_price is not None:
        return override_price, "override"

    median_val = safe_float(
        row.get("median") or
        row.get("discogs_median") or
        row.get("median_price")
    )

    if median_val is not None and median_val > 0:
        return round(median_val), "median"

    high_val = safe_float(
        row.get("high_sold") or
        row.get("discogs_high") or
        row.get("high_price")
    )

    if high_val is not None and high_val > 0:
        return round(high_val), "high_sold"

    return DEFAULT_PRICE, "default"

def main():
    print("store.py loaded (fixed indentation version)")

if __name__ == "__main__":
    main()
