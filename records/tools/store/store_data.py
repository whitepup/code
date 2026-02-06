#!/usr/bin/env python3
# store_data.py
# Discogs collection -> store_inventory.json + legacy index.html layout (unchanged)

from __future__ import annotations

import json
import os
import re
import time
import hashlib
import csv
from collections import defaultdict
from pathlib import Path
from typing import Optional
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request
import urllib.error

API_BASE = 

# ---- local asset helpers ----

def _md5_16(s: str) -> str:
    h = hashlib.md5(s.encode("utf-8", errors="ignore")).hexdigest()
    return h[:16]

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def download_image(url: str, out_path: Path, timeout: int = 30) -> bool:
    """Download url -> out_path if missing. Returns True if file exists after call."""
    try:
        if out_path.exists() and out_path.stat().st_size > 0:
            return True
    except Exception:
        pass
    if not url:
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "records-store/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        ensure_dir(out_path.parent)
        out_path.write_bytes(data)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False

def load_year_map(records_csv: Path) -> dict[int, str]:
    """Optional: offline_gallery records.csv -> {release_id:int: year:str}."""
    mp: dict[int, str] = {}
    if not records_csv.exists():
        return mp
    try:
        with records_csv.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            # try common column names
            for row in reader:
                rid_s = (row.get("release_id") or row.get("rid") or row.get("id") or "").strip()
                if not rid_s:
                    continue
                try:
                    rid = int(rid_s)
                except Exception:
                    continue
                year = (row.get("year") or row.get("released") or "").strip()
                if year:
                    mp[rid] = year
    except Exception:
        return mp
    return mp

def format_display(basic_information: dict) -> str:
    """Build a richer format string (e.g. Vinyl, 7\", 45 RPM, Single)."""
    formats = basic_information.get("formats") or []
    parts: list[str] = []
    if isinstance(formats, list):
        for f in formats:
            if not isinstance(f, dict):
                continue
            name = _norm(f.get("name") or "")
            desc = f.get("descriptions") or []
            dparts = []
            if isinstance(desc, list):
                for d in desc:
                    d = _norm(d)
                    if d:
                        dparts.append(d)
            text = _norm(f.get("text") or "")
            # keep compact
            seg = ", ".join([p for p in [name] + dparts + ([text] if text else []) if p])
            if seg:
                parts.append(seg)
    return " / ".join(parts) if parts else ""
"https://api.discogs.com"


# ---- env helpers (existing var names) ----

def env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return v

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()

def _norm_key(s: str) -> str:
    s = _norm(s).lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _make_key(artist: str, title: str) -> str:
    # Stable grouping key
    return f"{_norm_key(artist)}|{_norm_key(title)}"

# ---- .env loader for local runs (store.bat also loads; this is fallback) ----
def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        return

# ---- Discogs HTTP ----

def http_get_json(url: str, token: str, user_agent: str, sleep_s: float = 0.85) -> Tuple[Optional[Dict[str, Any]], Optional[int], Optional[str]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Authorization": f"Discogs token={token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read().decode("utf-8", errors="replace")
        time.sleep(sleep_s)
        return json.loads(body), status, None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        time.sleep(sleep_s)
        return None, int(getattr(e, "code", 0) or 0), (body[:500] if body else str(e))
    except Exception as e:
        time.sleep(sleep_s)
        return None, None, str(e)


def cached_http_get_json(url: str, token: str, user_agent: str, cache: Dict[str, Any], ttl_days: int, sleep_s: float = 0.0) -> Tuple[Optional[Dict[str, Any]], Optional[int], Optional[str]]:
    """Cache wrapper around http_get_json. Cache key is the full URL."""
    ent = cache.get(url) if isinstance(cache, dict) else None
    if isinstance(ent, dict):
        ts = ent.get("ts")
        if ts is not None and ttl_days is not None:
            try:
                if (time.time() - float(ts)) <= float(ttl_days) * 86400.0:
                    return ent.get("json"), ent.get("status"), ent.get("err")
            except Exception:
                pass
    # Miss or expired entry -> fetch from network and populate cache
    j, status, err = http_get_json(url, token, user_agent, sleep_s=sleep_s)
    if isinstance(cache, dict):
        cache[url] = {"ts": time.time(), "status": status, "err": err, "json": j}
    return j, status, err


def paged_releases(url: str, token: str, user_agent: str, per_page: int = 100) -> Tuple[List[Dict[str, Any]], Dict[str,int]]:
    out: List[Dict[str, Any]] = []
    page = 1
    stats = {"pages":0, "http_errors":0}
    while True:
        join = "&" if "?" in url else "?"
        u = f"{url}{join}per_page={per_page}&page={page}"
        data, status, err = http_get_json(u, token, user_agent)
        if data is None:
            stats["http_errors"] += 1
            break
        items = data.get("releases") or []
        if not items:
            break
        out.extend(items)
        stats["pages"] += 1
        pagination = data.get("pagination") or {}
        pages = pagination.get("pages")
        if pages is not None and page >= int(pages):
            break
        if pages is None and len(items) < per_page:
            break
        page += 1
    return out, stats

def parse_discogs_folders(s: str) -> List[Tuple[str, int]]:
    # "Personal:9057173,For Sale:9057166,Inbox:9061693"
    out: List[Tuple[str, int]] = []
    for part in [p.strip() for p in (s or "").split(",") if p.strip()]:
        if ":" not in part:
            continue
        name, fid = part.split(":", 1)
        name = name.strip()
        fid = fid.strip()
        try:
            out.append((name, int(fid)))
        except Exception:
            continue
    return out

def pick_folder(folders: List[Tuple[str,int]]) -> Tuple[str,int]:
    forced_id = env("STORE_FOLDER_ID")
    if forced_id:
        try:
            fid = int(forced_id)
            for n,i in folders:
                if i == fid:
                    return n,i
            return str(fid), fid
        except Exception:
            pass

    preferred = env("STORE_FOLDER_NAME")
    if preferred:
        for n,i in folders:
            if n.lower() == preferred.lower():
                return n,i

    for n,i in folders:
        if n.lower() == "for sale":
            return n,i

    return folders[0]

# ---- Marketplace median ----

def load_cache(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(path: Path, cache: Dict[str, Any]) -> None:
    path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

def get_median(release_id: int, token: str, user_agent: str, cache: Dict[str, Any], ttl_days: int, sleep_s: float = 0.95) -> Tuple[Optional[float], Optional[int], Optional[str]]:
    key = str(release_id)
    now = int(time.time())
    cached = cache.get(key)
    if isinstance(cached, dict):
        ts = int(cached.get("ts", 0) or 0)
        # Cache schema compatibility: only trust entries that include a median field.
        has_median = ("median" in cached) or ("median_usd" in cached)
        if ts and has_median and (now - ts) < ttl_days * 86400:
            # Support old key name median_usd from earlier scripts
            med = cached.get("median") if ("median" in cached) else cached.get("median_usd")
            return med, cached.get("status"), cached.get("err")

    url = f"{API_BASE}/marketplace/stats/{release_id}"
    data, status, err = cached_http_get_json(url, token, user_agent, cache, ttl_days, sleep_s=sleep_s)
    median_f: Optional[float] = None
    if data and isinstance(data, dict):
        m = data.get("median")
        if isinstance(m, dict):
            v = m.get("value")
            try:
                median_f = float(v) if v not in (None, "") else None
            except Exception:
                median_f = None

    cache[key] = {"ts": now, "median": median_f, "median_usd": median_f, "status": status, "err": err}
    return median_f, status, err

# ---- Build items in legacy schema ----

def build_items_from_discogs(releases: List[Dict[str, Any]], floor: float, token: str, user_agent: str, cache: Dict[str, Any], ttl_days: int, images_dir: Path, year_map: dict[int,str]) -> Tuple[List[dict], Dict[str,int]]:
    groups: Dict[str, dict] = {}
    by_key_rids: Dict[str, List[int]] = defaultdict(list)

    stats = {
        "rows": 0,
        "groups": 0,
        "median_ok": 0,
        "median_missing": 0,
        "median_errors": 0,
        "http_401": 0,
        "http_403": 0,
        "http_404": 0,
        "http_429": 0,
        "http_other": 0,
    }

    for r in releases:
        stats["rows"] += 1
        bi = r.get("basic_information") or {}
        rid = bi.get("id")
        if rid is None:
            continue
        try:
            rid_i = int(rid)
        except Exception:
            continue

        title = _norm(bi.get("title"))
        artists = bi.get("artists") or []
        artist = ""
        if isinstance(artists, list) and artists:
            artist = _norm(artists[0].get("name"))
        country = _norm(bi.get("country"))
        labels = bi.get("labels") or []
        label = _norm(labels[0].get("name")) if isinstance(labels, list) and labels else ""
        catno = _norm(labels[0].get("catno")) if isinstance(labels, list) and labels else ""

        # richer format (include 7\", 10\", 78 RPM, etc when present)
        fmt = format_display(bi) or _norm((bi.get("formats") or [{}])[0].get("name") if isinstance(bi.get("formats"), list) and bi.get("formats") else "")

        # year (prefer offline_gallery records.csv mapping when available)
        year = (year_map.get(rid_i) or str(bi.get("year") or "")).strip() or ""

        # cover image: prefer Discogs cover_image (usually higher-res than thumb)
        cover_url = _norm(bi.get("cover_image") or bi.get("thumb") or "")
        img_rel = ""
        if cover_url:
            try:
                ext = Path(urllib.parse.urlparse(cover_url).path).suffix.lower()
                if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                    ext = ".jpeg"
            except Exception:
                ext = ".jpeg"
            fn = _md5_16(cover_url) + ext
            out_path = images_dir / fn
            download_image(cover_url, out_path)
            img_rel = f"images/{fn}"

        key = _make_key(artist, title)
        by_key_rids[key].append(rid_i)

        if key not in groups:
            groups[key] = {
                "key": key,
                "artist": artist,
                "title": title,
                "year": year,
                "country": country,
                "label": label,
                "catno": catno,
                "format": fmt,
                "rid": str(rid_i),
                "img": img_rel or cover_url,
                "img_full_local": img_rel, "img_full_url": cover_url or "",
                "price": "",          # string per legacy
                "status": "available",
                "condition": "",
                "sleeve_condition": "",
                "notes": "",
            }

    # price each group using the first rid for that group
    for idx, (key, g) in enumerate(groups.items(), start=1):
        rid_i = int(g.get("rid") or 0)
        if idx == 1 or idx % 100 == 0:
            print(f"Pricing {idx}/{len(groups)} ...", flush=True)
        # Prefer Discogs price suggestions by condition (default VG)
        suggested = None
        sugg_url = f"{API_BASE}/marketplace/price_suggestions/{rid_i}"
        sugg_json, sugg_status, sugg_err = cached_http_get_json(sugg_url, token, user_agent, cache, ttl_days, sleep_s=0.95)
        if isinstance(sugg_json, dict):
            ps = sugg_json.get("price_suggestions")
            if ps is None:
                ps = sugg_json
            priority = ("Very Good (VG)", "Very Good Plus (VG+)", "Near Mint (NM or M-)", "Mint (M)")
            if isinstance(ps, dict):
                for cond in priority:
                    ent = ps.get(cond)
                    if isinstance(ent, dict):
                        v = ent.get("value")
                    else:
                        v = ent
                    try:
                        suggested = float(v) if v not in (None, "") else None
                    except Exception:
                        suggested = None
                    if suggested is not None:
                        break
            elif isinstance(ps, list):
                for cond in priority:
                    for row in ps:
                        if isinstance(row, dict) and row.get("condition") == cond:
                            v = row.get("value")
                            try:
                                suggested = float(v) if v not in (None, "") else None
                            except Exception:
                                suggested = None
                            break
                    if suggested is not None:
                        break
        
        if suggested is not None:
            if float(suggested) < floor:
                stats["median_missing"] += 1
                price = floor
            else:
                stats["median_ok"] += 1
                price = float(suggested)
        else:
            median, status, err = get_median(rid_i, token, user_agent, cache, ttl_days)
            if status == 401:
                stats["http_401"] += 1
            elif status == 403:
                stats["http_403"] += 1
            elif status == 404:
                stats["http_404"] += 1
            elif status == 429:
                stats["http_429"] += 1
            elif isinstance(status, int) and status >= 400:
                stats["http_other"] += 1
        
            if median is None:
                if status is None or (isinstance(status, int) and status >= 400):
                    stats["median_errors"] += 1
                else:
                    stats["median_missing"] += 1
                price = floor
            else:
                if float(median) < floor:
                    stats["median_missing"] += 1
                    price = floor
                else:
                    stats["median_ok"] += 1
                    price = float(median)
        g["price"] = str(int(round(price)))

    items = list(groups.values())
    items.sort(key=lambda x: ((x.get("artist") or "").lower(), (x.get("title") or "").lower()))
    stats["groups"] = len(items)
    return items, stats

# ---- Main ----

def main() -> int:
    # Allow running store.py directly without store.bat
    load_env_file(Path(r"D:\records\.env"))

    records_home = Path(env("RECORDS_HOME", r"D:\records"))
    records_out = Path(env("RECORDS_OUT", str(records_home / "outputs")))
    token = env("DISCOGS_TOKEN")
    username = env("DISCOGS_USERNAME") or env("DISCOGS_USER")
    user_agent = env("DISCOGS_USER_AGENT") or "untTool/1.0 +https://whitepup.github.io/store/"

    folders_str = env("DISCOGS_FOLDERS")
    floor = float(env("STORE_MIN_PRICE", "5") or "5")
    ttl_days = int(env("STORE_CACHE_TTL_DAYS", "14") or "14")

    if not token:
        print("ERROR: DISCOGS_TOKEN missing.", flush=True)
        return 2
    if not username:
        print("ERROR: DISCOGS_USERNAME/DISCOGS_USER missing.", flush=True)
        return 3
    if not folders_str:
        print("ERROR: DISCOGS_FOLDERS missing.", flush=True)
        return 4

    folders = parse_discogs_folders(folders_str)
    if not folders:
        print("ERROR: Could not parse DISCOGS_FOLDERS.", flush=True)
        return 5

    OUT_ROOT = records_out / "store"
    SITE_DIR = OUT_ROOT / "site"
    CACHE_PATH = OUT_ROOT / "cache.json"
    ensure_dir(SITE_DIR)
    IMAGES_DIR = SITE_DIR / "images"
    ensure_dir(IMAGES_DIR)

    # Optional: use offline_gallery years if available
    year_map = load_year_map(records_out / "offline_gallery" / "records.csv")

    print("=== Store Data Builder (Discogs fetch + pricing + inventory json) ===", flush=True)
    print(f"DISCOGS user: {username}", flush=True)
    print(f"Folders: {len(folders)}", flush=True)
    for fn, fid in folders:
        print(f"  - {fn} ({fid})", flush=True)
    print(f"Floor: ${int(floor)}", flush=True)
    print(f"Output site: {SITE_DIR}", flush=True)
    print(f"Cache: {CACHE_PATH}", flush=True)

    # Fetch releases across *all* folders listed in DISCOGS_FOLDERS, then de-dupe by release_id.
    releases_all: List[Dict[str, Any]] = []
    combined_stats = {"pages": 0, "http_errors": 0}
    for fn, fid in folders:
        releases_url = f"{API_BASE}/users/{urllib.parse.quote(username)}/collection/folders/{fid}/releases"
        rels, rel_stats = paged_releases(releases_url, token, user_agent, per_page=100)
        releases_all.extend(rels)
        combined_stats["pages"] += int(rel_stats.get("pages", 0) or 0)
        combined_stats["http_errors"] += int(rel_stats.get("http_errors", 0) or 0)
        print(f"Folder fetched: {fn} ({fid}) | pages: {rel_stats.get('pages',0)} | rows: {len(rels)} | http_errors: {rel_stats.get('http_errors',0)}", flush=True)

    # De-dupe by Discogs release_id (basic_information.id)
    seen_rids: set[int] = set()
    releases: List[Dict[str, Any]] = []
    dup_rows = 0
    for rr in releases_all:
        bi = rr.get("basic_information") or {}
        rid = bi.get("id")
        if rid is None:
            continue
        try:
            rid_i = int(rid)
        except Exception:
            continue
        if rid_i in seen_rids:
            dup_rows += 1
            continue
        seen_rids.add(rid_i)
        releases.append(rr)

    print(
        f"Collection API pages (sum): {combined_stats.get('pages',0)} | rows (raw): {len(releases_all)} | rows (dedup by release_id): {len(releases)} | dup_rows_dropped: {dup_rows} | http_errors (sum): {combined_stats.get('http_errors',0)}",
        flush=True,
    )
    # Quick live probe: attempt marketplace stats for first release_id to capture raw failure mode
    probe_rid = None
    for rr in releases:
        bi = rr.get("basic_information") or {}
        rid = bi.get("id")
        if rid is not None:
            try:
                probe_rid = int(rid)
                break
            except Exception:
                pass
    if probe_rid:
        probe_url = f"{API_BASE}/marketplace/stats/{probe_rid}"
        d, st, er = http_get_json(probe_url, token, user_agent, sleep_s=0.0)
        print(f"Marketplace probe rid={probe_rid} status={st} err={er}", flush=True)

    cache = load_cache(CACHE_PATH)
    items, price_stats = build_items_from_discogs(releases, floor, token, user_agent, cache, ttl_days, IMAGES_DIR, year_map)
    save_cache(CACHE_PATH, cache)

    inv_path = SITE_DIR / "store_inventory.json"
    inv_path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {inv_path}", flush=True)

    # Pricing diagnostics
    print("--- Pricing diagnostics ---", flush=True)
    # Always show up to 5 sample errors from marketplace stats calls
    if price_stats.get("median_errors", 0) > 0:
        samples = []
        for rid, v in cache.items():
            if isinstance(v, dict):
                err = v.get("err")
                status = v.get("status")
                if err:
                    samples.append((rid, status, err))
        if samples:
            print("sample_marketplace_errors:", flush=True)
            for rid, status, err in samples[:5]:
                print(f"  rid={rid} status={status} err={err}", flush=True)
        else:
            print("sample_marketplace_errors: (none recorded in cache)", flush=True)
    for k in ["groups","median_ok","median_missing","median_errors","http_401","http_403","http_404","http_429","http_other"]:
        print(f"{k}: {price_stats.get(k,0)}", flush=True)
    if price_stats.get("http_429",0) > 0:
        print("NOTE: HTTP 429 indicates rate limiting; rerun later or increase cache TTL.", flush=True)

    print("Done.", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())