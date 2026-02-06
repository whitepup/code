#!/usr/bin/env python3
# BUILD_ID: STOREPRICE_APPLY_V01
#
# Apply pricing_overrides.csv -> store_inventory.json
#
# Reads:
#   %RECORDS_HOME%\data\store\pricing_overrides.csv
# Writes (default):
#   %RECORDS_OUT%\store\site\store_inventory.json
#
# Matching:
#   item.variant_release_ids (preferred) else item.release_id
# Notes:
#   Preserves existing item.notes; appends a small marker when changed.
#
# Safe:
#   Creates timestamped backup of store_inventory.json before overwriting.

from __future__ import annotations
import csv
import json
import os
import time
from pathlib import Path
from typing import Dict, Any

def now_ts() -> str:
    return time.strftime("%Y%m%d-%H%M%S")

def load_pricing_overrides(path: Path) -> Dict[str, Dict[str, str]]:
    # returns map rid -> {price, notes}
    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
        r = csv.DictReader(f)
        out: Dict[str, Dict[str, str]] = {}
        for row in r:
            rid = (row.get("variant_release_ids") or "").strip()
            if not rid:
                continue
            price = (row.get("price") or "").strip()
            notes = (row.get("notes") or "").strip()
            if price:
                out[rid] = {"price": price, "notes": notes}
        return out

def main() -> int:
    records_home = Path(os.getenv("RECORDS_HOME", r"D:\records"))
    records_out  = Path(os.getenv("RECORDS_OUT",  str(records_home / "outputs")))
    data_dir = records_home / "data" / "store"
    pricing_csv = Path(os.getenv("PRICING_CSV", str(data_dir / "pricing_overrides.csv")))

    site_dir = Path(os.getenv("STORE_SITE_DIR", str(records_out / "store" / "site")))
    inv_json = Path(os.getenv("STORE_INVENTORY_JSON", str(site_dir / "store_inventory.json")))

    print("=== Apply Store Prices | BUILD_ID STOREPRICE_APPLY_V01 ===")
    print("RECORDS_HOME:", records_home)
    print("RECORDS_OUT: ", records_out)
    print("Pricing CSV:", pricing_csv)
    print("Inventory:  ", inv_json)
    print("")

    if not pricing_csv.exists():
        print("ERROR: missing pricing CSV:", pricing_csv)
        return 2
    if not inv_json.exists():
        print("ERROR: missing store_inventory.json:", inv_json)
        print("Hint: run the store generator first to create the site output.")
        return 2

    price_map = load_pricing_overrides(pricing_csv)
    print(f"Loaded pricing rows with price: {len(price_map)}")

    raw = inv_json.read_text(encoding="utf-8", errors="replace")
    inv = json.loads(raw)
    items = inv.get("items") or []
    if not isinstance(items, list):
        print("ERROR: inventory JSON has no 'items' list")
        return 2

    backup = inv_json.with_name(inv_json.stem + "_backup_" + now_ts() + inv_json.suffix)
    backup.write_text(raw, encoding="utf-8")
    print("Backup:", backup)

    matched = updated = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        rid = str(it.get("variant_release_ids") or "").strip()
        if not rid:
            rid = str(it.get("release_id") or "").strip()
        if not rid:
            continue
        pr = price_map.get(rid)
        if not pr:
            continue
        matched += 1

        old_price = str(it.get("price") or "").strip()
        new_price = str(pr.get("price") or "").strip()
        if not new_price:
            continue

        if old_price != new_price:
            it["price"] = new_price
            old_notes = str(it.get("notes") or "").strip()
            marker = "PRICE_APPLIED_FROM_OVERRIDES"
            if marker not in old_notes:
                it["notes"] = (old_notes + " | " + marker).strip(" |") if old_notes else marker
            updated += 1

    inv["items"] = items
    inv_json.parent.mkdir(parents=True, exist_ok=True)
    inv_json.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Matched items:", matched)
    print("Updated items:", updated)
    print("Wrote:", inv_json)
    print("Done.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
