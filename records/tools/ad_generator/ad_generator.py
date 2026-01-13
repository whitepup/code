#!/usr/bin/env python
"""
ad_generator.py

Genre mode logic:

  ✔ Prefer Pop when multiple genres present.
  ✔ If both Folk and Country present -> prefer Country.
  ✔ Special case: "Folk, World, & Country" (and variants) is split into:
        Folk_World (first ~2/3 of records)
        Country   (last ~1/3)
  ✔ Tiny genres (<36 covers) are merged into Misc.
  ✔ Per-artist majority genre:
        For each artist, we look at ALL their records' broad genres
        (after the Pop/Country preference step) and assign the artist
        to the genre where MOST of their records fall.
        Then ALL of their records go into that majority genre bucket.

        Example:
          Anne Murray:
            records genres: ["Country", "Country", "Rock"]
            majority = Country
            => all three go into "Country".

  ✔ One square grid per genre (including Misc), flat output directory.
"""

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    print("This script requires Pillow: pip install pillow")
    sys.exit(1)


# ---------- Helpers for genre selection ----------

def choose_broad_genre(raw):
    """
    Pick a single broad genre with priority:
      1) If multiple & Pop present -> Pop
      2) If both Folk and Country present -> Country
      3) Else first/only entry

    raw may be a string or a list.
    """
    # List case
    if isinstance(raw, list):
        strs = [str(x).strip() for x in raw if str(x).strip()]
        lows = [s.lower() for s in strs]
        if len(strs) > 1:
            # Prefer Pop
            if any("pop" in s for s in lows):
                return "Pop"
            # Prefer Country if Folk & Country both present
            if any("folk" in s for s in lows) and any("country" in s for s in lows):
                return "Country"
        return strs[0] if strs else None

    # String case
    s = str(raw).strip()
    if not s:
        return None

    low = s.lower()
    # Only treat as multi-genre if obvious separators appear
    if any(sep in s for sep in [",", "/", "&", ";", "|"]):
        if "pop" in low:
            return "Pop"
        if ("folk" in low) and ("country" in low):
            return "Country"

    return s


def normalize_genre_key(g: str) -> str:
    """
    Normalize for composite detection, e.g. "Folk, World, & Country" -> "folk_world_country".
    """
    s = g.strip().lower()
    s = "".join(ch if ch.isalnum() else " " for ch in s)
    parts = [p for p in s.split() if p]
    return "_".join(parts)


def safe_slug(name: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in name).strip("_") or "Unknown"


# ---------- Record extraction with artist + broad genre ----------

def extract_artist(rec: dict):
    """
    Try to pull an artist name from typical fields.
    """
    for k in ("artist", "artist_name", "artists"):
        if k in rec and rec[k]:
            v = rec[k]
            if isinstance(v, list):
                return str(v[0]).strip()
            return str(v).strip()
    return None


def load_records(images_dir: Path, inv_path: Path):
    """
    Return a list of (artist, broad_genre, image_path) tuples based on
    the inventory JSON, applying Pop/Country preferences but NOT yet
    doing Folk_World_Country split or tiny-genre merging.
    """
    raw = json.loads(inv_path.read_text(encoding="utf-8"))
    records_src = raw.get("records") or raw.get("items") or raw.get("data") or raw
    if not isinstance(records_src, list):
        return []

    out = []

    for rec in records_src:
        if not isinstance(rec, dict):
            continue

        # Broad genre value (could be list or string)
        g_val = None
        for k in ("broad_genre", "genre_broad", "genre_group", "genre"):
            if k in rec and rec[k]:
                g_val = rec[k]
                break
        if g_val is None:
            continue

        broad = choose_broad_genre(g_val)
        if not broad:
            continue

        # Image path
        img_val = None
        for k in ("img", "image_path", "cover_image", "image", "cover"):
            if k in rec and rec[k]:
                img_val = rec[k]
                break
        if not img_val:
            continue

        p = Path(str(img_val))
        if not p.is_absolute():
            parts = list(p.parts)
            if parts and parts[0].lower() == images_dir.name.lower():
                parts = parts[1:]
            p = images_dir.joinpath(*parts) if parts else images_dir / img_val

        if not p.exists():
            continue

        artist = extract_artist(rec) or None
        out.append((artist, broad, p))

    return out


# ---------- Grid rendering ----------

def create_single_square_grid(images, outdir: Path, tile: int, prefix: str):
    """
    One square grid for this set of images:
      side = ceil(sqrt(N))
      filled with random covers if needed.
    """
    if not images:
        return

    from PIL import Image, ImageOps

    n = len(images)
    side = max(1, math.ceil(math.sqrt(n)))
    cols = rows = side
    need = cols * rows

    batch = list(images)
    if len(batch) < need:
        for _ in range(need - len(batch)):
            batch.append(random.choice(images))

    canvas = Image.new("RGB", (cols * tile, rows * tile), "white")

    for i, pth in enumerate(batch):
        r = i // cols
        c = i % cols
        try:
            with Image.open(pth) as im:
                th = ImageOps.fit(im.convert("RGB"), (tile - 2, tile - 2))
            canvas.paste(th, (c * tile + 1, r * tile + 1))
        except Exception:
            continue

    outdir.mkdir(parents=True, exist_ok=True)
    op = outdir / f"{prefix}_grid_{cols}x{rows}.jpg"
    canvas.save(op, format="JPEG", quality=90)
    print(f"Wrote: {op} (n={n}, grid={cols}x{rows})")


# ---------- Main genre-mode pipeline ----------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("genre", help="Per-genre single grids with per-artist majority genre")
    pg.add_argument("--images-dir", default=".")
    pg.add_argument("--inventory-json", required=True)
    pg.add_argument("--output-dir", default="ads_by_genre")
    pg.add_argument("--tile", type=int, default=192)

    args = ap.parse_args()
    if args.cmd != "genre":
        return

    images_dir = Path(args.images_dir)
    inv = Path(args.inventory_json)

    records = load_records(images_dir, inv)
    if not records:
        print("No usable records found in inventory JSON.")
        return

    # --- Per-artist majority genre ---
    artist_counts = defaultdict(lambda: defaultdict(int))
    for artist, broad, _ in records:
        if not artist:
            continue
        artist_counts[artist][broad] += 1

    artist_major = {}
    for artist, counts in artist_counts.items():
        # Pick genre with highest count; tie-breaker = first encountered
        major = max(counts.items(), key=lambda kv: kv[1])[0]
        artist_major[artist] = major

    # Build initial genre -> covers using artist-major override
    genre_map = defaultdict(list)
    for artist, broad, img_path in records:
        final_genre = artist_major.get(artist, broad)
        genre_map[final_genre].append(img_path)

    # --- Special split: Folk/World/Country composite ---
    split = defaultdict(list)
    for g, covers in genre_map.items():
        key = normalize_genre_key(g)
        if key == "folk_world_country":
            n = len(covers)
            cut = max(1, (2 * n) // 3)
            split["Folk_World"].extend(covers[:cut])
            split["Country"].extend(covers[cut:])
        else:
            split[g].extend(covers)

    # --- Merge tiny genres into Misc ---
    misc = []
    big = {}
    for g, covers in split.items():
        if len(covers) < 36:
            misc.extend(covers)
        else:
            big[g] = covers

    if misc:
        big["Misc"] = big.get("Misc", []) + misc

    if not big:
        print("After merging tiny genres, nothing left to render.")
        return

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for g, covers in sorted(big.items(), key=lambda kv: kv[0].lower()):
        slug = safe_slug(g)
        print(f"{g}: {len(covers)} covers -> saving...")
        create_single_square_grid(covers, out, args.tile, slug)


if __name__ == "__main__":
    main()
