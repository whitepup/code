
# hunt.py - MASTER-LEVEL COVERS with disc-label avoidance
# BUILD_ID: HUNT_20260109_COVERS_V4
#
# - Reads per-decade *_top_sellers_*.csv from data_backups
# - For each release_id, calls Discogs /releases/{id}
# - Chooses the BEST cover image by:
#     * considering ALL images
#     * strongly preferring non-label images (disc-label heuristic)
#     * then preferring type == "primary"
# - Saves covers into D:\records\outputs\hunt\covers
# - Builds simple HTML pages per decade (thumbnails + artist/title)
#
# NOTE: This script intentionally has no collection writes.

import csv
import io
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests

try:
    import openpyxl  # only used when reading .xlsx fallback
except ImportError:
    openpyxl = None

# Load .env so DISCOGS_* vars are available
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(r"D:\records\.env"))
except Exception:
    pass

# Optional image libs for disc-label detection
try:
    from PIL import Image
    import numpy as np
except ImportError:  # if missing, we still run but without label detection
    Image = None
    np = None

# ---------- paths ----------

REPO_ROOT = Path(r"C:\Users\David\Documents\GitHub\code\records")
INPUT_DIR = REPO_ROOT / "data_backups"

RUNTIME_ROOT = Path(r"D:\records")
OUTPUT_DIR = RUNTIME_ROOT / "outputs" / "hunt"
COVERS_DIR = OUTPUT_DIR / "covers"


# ---------- logging ----------

def setup_logging() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT_DIR / "hunt.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("=== hunt.py starting (BUILD_ID=HUNT_20260109_COVERS_V4) ===")
    logging.info("  INPUT_DIR=%s", INPUT_DIR)
    logging.info("  OUTPUT_DIR=%s", OUTPUT_DIR)


# ---------- Discogs client ----------

TOKEN = os.getenv("DISCOGS_TOKEN", "").strip()
USER = os.getenv("DISCOGS_USERNAME", "").strip()
UA = os.getenv("DISCOGS_USER_AGENT", "").strip() or "HuntCovers/1.0 +https://whitepup.github.io/store/"


class Client:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers.update(
            {
                "User-Agent": UA,
                "Authorization": f"Discogs token={TOKEN}",
            }
        )
        self.base = "https://api.discogs.com"

    def get_release(self, rid: int) -> Dict:
        url = f"{self.base}/releases/{rid}"
        for attempt in range(3):
            try:
                r = self.s.get(url, timeout=30)
            except Exception as e:
                logging.warning("get_release %s network error (%s)", rid, e)
                time.sleep(2)
                continue

            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "5")) + 1
                logging.info("get_release %s 429 -> sleeping %ss", rid, wait)
                time.sleep(wait)
                continue

            if r.status_code >= 400:
                logging.warning("get_release %s HTTP %s %s", rid, r.status_code, r.text[:200])
                return {}

            try:
                return r.json()
            except Exception as e:
                logging.warning("get_release %s JSON error: %s", rid, e)
                return {}
        return {}


# ---------- helpers for input ----------

def infer_decade(p: Path) -> str:
    m = re.search(r"(19[0-9]{2}s|20[0-9]{2}s)", p.name)
    return m.group(1) if m else "unknown"


def find_input_files() -> List[Path]:
    if not INPUT_DIR.exists():
        logging.warning("INPUT_DIR does not exist: %s", INPUT_DIR)
        return []
    files: List[Path] = []
    files += sorted(INPUT_DIR.glob("*_top_sellers_*.xlsx"))
    files += sorted(INPUT_DIR.glob("*_top_sellers_*.csv"))
    logging.info("Found %d input files", len(files))
    return files


def read_xlsx(p: Path) -> List[Dict]:
    if openpyxl is None:
        logging.error("openpyxl not installed, cannot read %s", p)
        return []
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    ws = wb.active
    head = [c for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    out: List[Dict] = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        row = {str(head[i]): r[i] for i in range(len(head))}
        out.append(row)
    logging.info("  Loaded %d from %s", len(out), p.name)
    return out


def read_csv(p: Path) -> List[Dict]:
    out: List[Dict] = []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            out.append(r)
    logging.info("  Loaded %d from %s", len(out), p.name)
    return out


def extract_release_id(row: Dict) -> int | None:
    for k in ("discogs_id", "release_id", "id", "release"):
        if k in row and row[k] not in (None, ""):
            try:
                return int(str(row[k]).strip())
            except Exception:
                pass
    return None


# ---------- disc-label heuristic ----------

# Normalized coordinates (x,y in [0,1]) for green (outer ring) & red (label)
GREEN_POINTS: Tuple[Tuple[float, float], ...] = (
    (0.2775, 0.0292),
    (0.7492, 0.0309),
    (0.0367, 0.0326),
    (0.9575, 0.0433),
    (0.1283, 0.1183),
    (0.0418, 0.2283),
    (0.9668, 0.2568),
    (0.0442, 0.7492),
    (0.9525, 0.7683),
    (0.1325, 0.8684),
    (0.2383, 0.9558),
    (0.9417, 0.9609),
    (0.0426, 0.9683),
    (0.7458, 0.9625),
)

RED_POINTS: Tuple[Tuple[float, float], ...] = (
    (0.5102, 0.0891),
    (0.7766, 0.1975),
    (0.2182, 0.2016),
    (0.4234, 0.2658),
    (0.5903, 0.2715),
    (0.6853, 0.3735),
    (0.3101, 0.4502),
    (0.0901, 0.5191),
    (0.9043, 0.5332),
    (0.6941, 0.5875),
    (0.3826, 0.6704),
    (0.5843, 0.7008),
    (0.2215, 0.8002),
    (0.7592, 0.8135),
    (0.4859, 0.8980),
)

WINDOW_FRAC = 0.02
GREEN_STD_MAX = 20.0
MEAN_DIST_MIN = 60.0

CORNER_DIFF_MIN = 25.0   # center must be at least this much brighter than corners
CORNER_STD_MAX = 40.0    # corners relatively uniform (vinyl black)


def _sample_colors(arr, points) -> Tuple["np.ndarray", bool]:
    """
    Sample mean RGB colors around each normalized point.
    Returns (N,3) array and bool indicating if we got enough samples.
    """
    h, w, _ = arr.shape
    rad = max(1, int(WINDOW_FRAC * min(w, h)))
    samples = []

    for nx, ny in points:
        cx = int(nx * (w - 1))
        cy = int(ny * (h - 1))
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            continue
        x0 = max(0, cx - rad)
        x1 = min(w, cx + rad + 1)
        y0 = max(0, cy - rad)
        y1 = min(h, cy + rad + 1)
        patch = arr[y0:y1, x0:x1, :]
        if patch.size == 0:
            continue
        mean_color = patch.reshape(-1, 3).mean(axis=0)
        samples.append(mean_color)

    if not samples:
        return np.zeros((0, 3), dtype=np.float32), False

    samples_arr = np.vstack(samples).astype(np.float32)
    enough = samples_arr.shape[0] >= len(points) * 0.6
    return samples_arr, enough


def looks_like_disc_label(image_bytes: bytes) -> bool:
    """
    Return True if the image strongly matches a disc label pattern.

    We use two cues:
      1) Ring vs center color (GREEN/RED sample points)
      2) Bright center vs dark, uniform corners (7"/12" vinyl look)

    If Pillow/numpy are missing or something fails, returns False (never blocks).
    """
    if Image is None or np is None:
        return False

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return False

    w, h = im.size
    if w < 200 or h < 200:
        # very small image – treat as not a label to avoid false positives
        return False

    arr = np.asarray(im)

    # --- heuristic 1: ring vs center ---
    green_samples, enough_green = _sample_colors(arr, GREEN_POINTS)
    red_samples, enough_red = _sample_colors(arr, RED_POINTS)
    ring_label = False
    if enough_green and enough_red:
        green_mean = green_samples.mean(axis=0)
        red_mean = red_samples.mean(axis=0)
        green_std = green_samples.std(axis=0).mean()
        mean_dist = float(np.linalg.norm(green_mean - red_mean))
        if green_std <= GREEN_STD_MAX and mean_dist >= MEAN_DIST_MIN:
            ring_label = True

    # --- heuristic 2: dark corners vs bright center (vinyl rim) ---
    # convert to grayscale
    gray = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]).astype(np.float32)
    rad = max(1, int(WINDOW_FRAC * min(w, h)) * 2)

    # corners
    h2, w2 = gray.shape
    corners = []
    # top-left
    corners.append(gray[0:rad, 0:rad])
    # top-right
    corners.append(gray[0:rad, max(0, w2 - rad):w2])
    # bottom-left
    corners.append(gray[max(0, h2 - rad):h2, 0:rad])
    # bottom-right
    corners.append(gray[max(0, h2 - rad):h2, max(0, w2 - rad):w2])

    corner_vals = np.concatenate([c.reshape(-1) for c in corners if c.size > 0]) if corners else np.array([], dtype=np.float32)

    # center
    cx = w2 // 2
    cy = h2 // 2
    x0 = max(0, cx - rad)
    x1 = min(w2, cx + rad)
    y0 = max(0, cy - rad)
    y1 = min(h2, cy + rad)
    center_patch = gray[y0:y1, x0:x1]

    corner_label = False
    if corner_vals.size > 0 and center_patch.size > 0:
        corner_mean = float(corner_vals.mean())
        center_mean = float(center_patch.mean())
        corner_std = float(corner_vals.std())
        diff = center_mean - corner_mean  # positive if center is brighter
        if diff >= CORNER_DIFF_MIN and corner_std <= CORNER_STD_MAX:
            corner_label = True

    return ring_label or corner_label


# ---------- image download / cover selection ----------

def download_image(url: str, dest: Path) -> bool:
    """
    Download full-resolution image to dest.
    """
    try:
        r = requests.get(url, timeout=60, stream=True, headers={"User-Agent": UA})
        if r.status_code != 200:
            logging.warning("Image download %s -> HTTP %s", url, r.status_code)
            return False
        with dest.open("wb") as f:
            for chunk in r.iter_content(8192):
                if not chunk:
                    continue
                f.write(chunk)
        return True
    except Exception as e:
        logging.warning("Image download error %s -> %s", url, e)
        return False


def choose_cover(rel: Dict) -> str:
    """
    Choose the best cover image URL for a release.
    Logic:
      1) Consider all images from rel["images"].
      2) For each image, fetch its thumbnail (uri150 or uri) into memory.
      3) Run looks_like_disc_label() on the thumbnail bytes.
      4) Rank images by:
           - non-label first (label images go to bottom)
           - type == 'primary' preferred
           - then original index order
      5) Return the full-size URL (uri or resource_url) of the best image.
    If anything fails, fall back to previous behavior: primary image then first.
    """
    images = rel.get("images") or []
    if not images:
        return ""

    # If we can't run label detection, just prefer primary then first
    if Image is None or np is None:
        primary = None
        for img in images:
            if str(img.get("type", "")).lower() == "primary":
                primary = img
                break
        img = primary or images[0]
        return img.get("uri") or img.get("resource_url") or ""

    scored_candidates: List[Tuple[int, int, int, str]] = []  # (is_label, is_not_primary, idx, full_url)

    for idx, img in enumerate(images):
        full_url = img.get("uri") or img.get("resource_url") or ""
        thumb_url = img.get("uri150") or full_url
        if not full_url or not thumb_url:
            continue

        # Download thumbnail bytes for label detection
        try:
            r = requests.get(thumb_url, timeout=30, headers={"User-Agent": UA})
            if r.status_code != 200:
                logging.warning("Thumb download %s -> HTTP %s", thumb_url, r.status_code)
                is_label = 0  # don't penalize on failure
            else:
                is_label = 1 if looks_like_disc_label(r.content) else 0
        except Exception as e:
            logging.warning("Thumb download error %s -> %s", thumb_url, e)
            is_label = 0  # don't penalize on failure

        img_type = str(img.get("type", "")).lower()
        is_not_primary = 0 if img_type == "primary" else 1

        scored_candidates.append((is_label, is_not_primary, idx, full_url))

    if not scored_candidates:
        return ""

    scored_candidates.sort()
    # Best candidate = first after sorting
    _, _, _, best_url = scored_candidates[0]
    return best_url


# ---------- HTML writer ----------

def write_html(all_items: Dict[str, List[Dict]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    # Index page
    idx = OUTPUT_DIR / "index.html"
    decades = sorted(all_items.keys())
    lines = ["<html><body><h1>Top Sellers (COVERS)</h1>"]
    for d in decades:
        lines.append(f"<a href='{d}.html'>{d}</a><br>")
    lines.append("</body></html>")
    idx.write_text("\n".join(lines), encoding="utf-8")

    # Per-decade pages
    for decade_label, items in all_items.items():
        p = OUTPUT_DIR / f"{decade_label}.html"
        body = ["<html><body>", f"<h1>{decade_label}</h1>", "<ul>"]
        for it in items:
            img = it.get("img_local")
            pic = f"<img src='{img}' height='80'>" if img else ""
            artist = it.get("artist", "?")
            title = it.get("title", "?")
            body.append(f"<li>{pic} {artist} — {title}</li>")
        body.append("</ul></body></html>")
        p.write_text("\n".join(body), encoding="utf-8")


# ---------- main ----------

def main() -> None:
    setup_logging()

    if not TOKEN or not USER:
        logging.error("DISCOGS_TOKEN or DISCOGS_USERNAME missing from environment.")
        logging.error("Make sure D:\\records\\.env exists and has DISCOGS_TOKEN / DISCOGS_USERNAME.")
        return

    client = Client()
    files = find_input_files()
    if not files:
        logging.warning("No input files found; nothing to do.")
        return

    cache: Dict[int, Dict] = {}
    by_decade: Dict[str, List[Dict]] = {}

    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    for path in files:
        decade_label = infer_decade(path)
        by_decade.setdefault(decade_label, [])

        if path.suffix.lower() == ".csv":
            rows = read_csv(path)
        else:
            rows = read_xlsx(path)

        for row in rows:
            rid = extract_release_id(row)
            if not rid:
                continue

            if rid not in cache:
                cache[rid] = client.get_release(rid)
                time.sleep(0.4)
            rel = cache.get(rid) or {}

            title = (rel.get("title") or row.get("title") or "").strip()
            arts = rel.get("artists") or []
            if arts:
                artist = ", ".join(a.get("name", "") for a in arts)
            else:
                artist = (row.get("artist") or "").strip()

            img_local = None
            url = choose_cover(rel)
            if url:
                fname = f"{rid}.jpg"
                dest = COVERS_DIR / fname
                if not dest.exists():
                    if download_image(url, dest):
                        logging.info("Saved cover %s for release %s", fname, rid)
                if dest.exists():
                    img_local = f"covers/{fname}"

            by_decade[decade_label].append({"title": title, "artist": artist, "img_local": img_local})

    write_html(by_decade)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
