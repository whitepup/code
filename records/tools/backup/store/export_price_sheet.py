#!/usr/bin/env python3
# BUILD_ID: 20251219_PRICE_V01

from __future__ import annotations
import csv
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

RECORDS_HOME = Path(os.getenv("RECORDS_HOME", r"D:\records"))
ENV_PATH = RECORDS_HOME / ".env"
load_dotenv(ENV_PATH, override=True)

RECORDS_OUT = Path(os.getenv("RECORDS_OUT", r"D:\records\outputs"))

OFFLINE_OUT = RECORDS_OUT / "offline_gallery"
DATA_DIR = RECORDS_HOME / "data" / "store"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PRICE_FILE = DATA_DIR / "pricing_overrides.csv"

def _norm(s: str) -> str:
    return (s or "").strip()

def _key_artist_title(artist: str, title: str) -> str:
    def n(x: str) -> str:
        x = (x or "").strip().lower()
        x = re.sub(r"\s+", " ", x)
        return x
    return n(artist) + "||" + n(title)

def _safe_int_year(y: str) -> Optional[int]:
    s = (y or "").strip()
    if not s:
        return None
    s = re.sub(r"\.0$", "", s)
    if not s.isdigit():
        return None
    v = int(s)
    if v < 1800 or v > 2100:
        return None
    return v

def _choose_year(years: List[Optional[int]]) -> Optional[int]:
    ys = [y for y in years if isinstance(y, int)]
    return min(ys) if ys else None

def load_existing(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    out: Dict[str, dict] = {}
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            key = _norm(row.get("key",""))
            if not key:
                continue
            out[key] = {
                "price": _norm(row.get("price","")),
                "status": _norm(row.get("status","")),
                "condition": _norm(row.get("condition","")),
                "sleeve_condition": _norm(row.get("sleeve_condition","")),
                "notes": _norm(row.get("notes","")),
            }
    return out

def main() -> int:
    records_csv = OFFLINE_OUT / "records.csv"
    if not records_csv.exists():
        raise SystemExit(f"Missing: {records_csv} (run offline gallery first)")

    existing = load_existing(PRICE_FILE)

    groups: Dict[str, dict] = {}
    years_by_key: Dict[str, List[Optional[int]]] = defaultdict(list)

    with records_csv.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder = _norm(row.get("folder",""))
            if folder.lower() != "for sale":
                continue
            rid = _norm(row.get("release_id",""))
            if not rid:
                continue
            artist = _norm(row.get("artist",""))
            title = _norm(row.get("title",""))
            if not artist and not title:
                continue

            key = _key_artist_title(artist, title)
            years_by_key[key].append(_safe_int_year(_norm(row.get("year",""))))

            if key not in groups:
                groups[key] = {
                    "key": key,
                    "artist": artist,
                    "title": title,
                    "year": "",
                    "qty": 1,
                    "variant_release_ids": rid,
                    "price": "",
                    "status": "",
                    "condition": "",
                    "sleeve_condition": "",
                    "notes": "",
                }
            else:
                groups[key]["qty"] = int(groups[key]["qty"]) + 1
                groups[key]["variant_release_ids"] = groups[key]["variant_release_ids"] + " " + rid

    rows: List[dict] = []
    for key, g in groups.items():
        y = _choose_year(years_by_key.get(key, []))
        g["year"] = str(y) if y else ""
        if key in existing:
            for fld in ("price","status","condition","sleeve_condition","notes"):
                if existing[key].get(fld):
                    g[fld] = existing[key][fld]
        rows.append(g)

    rows.sort(key=lambda x: ((x.get("artist","").lower()), (x.get("title","").lower())))

    fieldnames = ["key","artist","title","year","qty","variant_release_ids","price","status","condition","sleeve_condition","notes"]
    with PRICE_FILE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote: {PRICE_FILE} (rows={len(rows)})")
    print("Edit this file to add prices/status/notes. Then rebuild Store.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
