
import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

import requests


# ---------------------- logging setup ----------------------


def setup_logging(log_name: str) -> None:
    """
    Tee stdout/stderr to a log file under D:\\records\\outputs\\hunt.
    """
    log_dir = Path("D:/records/outputs/hunt")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_name

    class Tee:
        def __init__(self, stream, file_path: Path) -> None:
            self.stream = stream
            self.file = file_path.open("a", encoding="utf-8")

        def write(self, data: str) -> None:
            self.stream.write(data)
            self.file.write(data)

        def flush(self) -> None:
            self.stream.flush()
            self.file.flush()

    sys.stdout = Tee(sys.stdout, log_path)
    sys.stderr = Tee(sys.stderr, log_path)


setup_logging("hunt_build_top_sellers.log")


# ---------------------- config / env ----------------------


def load_env_d_records() -> None:
    """
    Always load Discogs credentials from D:\\records\\.env.
    """
    env_path = Path("D:/records/.env")
    if not env_path.exists():
        raise SystemExit(
            "Missing D:\\records\\.env. Please create it with at least:\n"
            "  DISCOGS_TOKEN=...\n"
            "  DISCOGS_USERNAME=...\n"
            "  DISCOGS_USER_AGENT=HuntTopSellers/1.0 +https://whitepup.github.io/store/\n"
        )
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            os.environ[key] = val


# ---------------------- Discogs client ----------------------


class DiscogsClient:
    def __init__(
        self,
        token: str,
        username: str,
        user_agent: str,
        delay: float = 1.0,
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.token = token
        self.username = username
        self.user_agent = user_agent or "HuntTopSellers/1.0 +https://whitepup.github.io/store/"
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        self.cache_dir = cache_dir or Path("D:/records/outputs/hunt")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.search_cache_path = self.cache_dir / "hunt_search_cache.json"
        self.price_cache_path = self.cache_dir / "hunt_price_cache.json"

        self._search_cache: Dict[str, dict] = {}
        self._price_cache: Dict[str, dict] = {}
        if self.search_cache_path.exists():
            try:
                self._search_cache = json.loads(self.search_cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._search_cache = {}
        if self.price_cache_path.exists():
            try:
                self._price_cache = json.loads(self.price_cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._price_cache = {}

    def _save_search_cache(self) -> None:
        try:
            self.search_cache_path.write_text(
                json.dumps(self._search_cache, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _save_price_cache(self) -> None:
        try:
            self.price_cache_path.write_text(
                json.dumps(self._price_cache, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ---------- helpers ----------

    def _search_key(self, year: int, page: int) -> str:
        return f"year:{year}|page:{page}"

    def search_year_page(
        self, year: int, page: int, per_page: int = 100
    ) -> List[dict]:
        """
        Search Discogs database for a given year/page with filters:
          - type=release
          - format=Vinyl
          - country=US
          - sort=want desc

        Uses a small cache so re-runs don't hammer the API.
        """
        key = self._search_key(year, page)
        if key in self._search_cache:
            return self._search_cache[key].get("results", [])

        params = {
            "token": self.token,
            "type": "release",
            "format": "Vinyl",
            "country": "US",
            "year": year,
            "per_page": per_page,
            "page": page,
            "sort": "want",
            "sort_order": "desc",
        }

        max_tries = 3
        base_sleep = max(self.delay, 0.7)
        last_error: Optional[Exception] = None

        for attempt in range(1, max_tries + 1):
            try:
                resp = self.session.get(
                    "https://api.discogs.com/database/search",
                    params=params,
                    timeout=30,
                )
            except Exception as e:
                last_error = e
                print(
                    f"  [Discogs] search network error (year={year}, page={page}) "
                    f"(attempt {attempt}/{max_tries}): {e}"
                )
                if attempt < max_tries:
                    time.sleep(base_sleep * attempt)
                    continue
                self._search_cache[key] = {"results": []}
                self._save_search_cache()
                return []

            if resp.status_code == 429:
                print(
                    f"  [Discogs] 429 Too Many Requests for year={year}, page={page} "
                    f"(attempt {attempt}/{max_tries}) - backing off..."
                )
                if attempt < max_tries:
                    time.sleep(base_sleep * (attempt * 4))
                    continue
                self._search_cache[key] = {"results": []}
                self._save_search_cache()
                return []

            try:
                resp.raise_for_status()
            except Exception as e:
                last_error = e
                print(
                    f"  [Discogs] search failed (year={year}, page={page}) "
                    f"status {resp.status_code}: {e}"
                )
                self._search_cache[key] = {"results": []}
                self._save_search_cache()
                return []

            data = resp.json()
            results = data.get("results") or []
            self._search_cache[key] = {"results": results}
            self._save_search_cache()
            if self.delay > 0:
                time.sleep(self.delay)
            return results

        print(f"  [Discogs] search ultimately failed (year={year}, page={page}): {last_error}")
        self._search_cache[key] = {"results": []}
        self._save_search_cache()
        return []

    def get_price_suggestions(self, release_id: int) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Fetch price suggestions for a release.

        Returns (low_price, med_price, high_price) based on:
          - low:  'G+'
          - med:  'VG+'
          - high: 'NM or M-'
        """
        key = str(release_id)
        cached = self._price_cache.get(key)
        if cached is not None:
            return (
                cached.get("low"),
                cached.get("med"),
                cached.get("high"),
            )

        url = f"https://api.discogs.com/marketplace/price_suggestions/{release_id}"
        params = {"token": self.token}

        max_tries = 3
        base_sleep = max(self.delay, 0.7)
        last_error: Optional[Exception] = None

        for attempt in range(1, max_tries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except Exception as e:
                last_error = e
                print(
                    f"  [Discogs] price_suggestions network error (release={release_id}) "
                    f"(attempt {attempt}/{max_tries}): {e}"
                )
                if attempt < max_tries:
                    time.sleep(base_sleep * attempt)
                    continue
                self._price_cache[key] = {"low": None, "med": None, "high": None}
                self._save_price_cache()
                return None, None, None

            if resp.status_code == 404:
                self._price_cache[key] = {"low": None, "med": None, "high": None}
                self._save_price_cache()
                return None, None, None

            if resp.status_code == 429:
                print(
                    f"  [Discogs] 429 Too Many Requests on price_suggestions "
                    f"(release={release_id}, attempt {attempt}/{max_tries})"
                )
                if attempt < max_tries:
                    time.sleep(base_sleep * (attempt * 4))
                    continue
                self._price_cache[key] = {"low": None, "med": None, "high": None}
                self._save_price_cache()
                return None, None, None

            try:
                resp.raise_for_status()
            except Exception as e:
                last_error = e
                print(
                    f"  [Discogs] price_suggestions failed (release={release_id}) "
                    f"status {resp.status_code}: {e}"
                )
                self._price_cache[key] = {"low": None, "med": None, "high": None}
                self._save_price_cache()
                return None, None, None

            data = resp.json() or {}
            def v(key_name: str) -> Optional[float]:
                entry = data.get(key_name)
                if isinstance(entry, dict):
                    return entry.get("value")
                return None

            low = v("G+")
            med = v("VG+")
            high = v("NM or M-")

            self._price_cache[key] = {"low": low, "med": med, "high": high}
            self._save_price_cache()
            if self.delay > 0:
                time.sleep(self.delay * 0.5)
            return low, med, high

        print(f"  [Discogs] price_suggestions ultimately failed (release={release_id}): {last_error}")
        self._price_cache[key] = {"low": None, "med": None, "high": None}
        self._save_price_cache()
        return None, None, None


# ---------------------- data model ----------------------


@dataclass
class TopSeller:
    release_id: int
    year: int
    artist: str
    title: str
    want: int
    have: int
    rating: float   # 0.0–1.0
    decade_label: str
    low_price: Optional[float] = None
    med_price: Optional[float] = None
    high_price: Optional[float] = None


# ---------------------- core logic ----------------------


def compute_rating(want: int, have: int) -> float:
    """
    Rating = want / (want + have), clamped to [0, 1].
    Gives 100% when all interest is wants and none are haves.
    """
    total = want + have
    if total <= 0:
        return 0.0
    r = want / float(total)
    if r < 0:
        return 0.0
    if r > 1:
        return 1.0
    return r


def collect_for_decade(
    client: DiscogsClient,
    decade_start: int,
    limit: int,
    max_pages_per_year: int = 5,
    per_page: int = 100,
) -> List[TopSeller]:
    """
    Build a candidate pool for a decade by scanning each year in [decade_start, decade_start+9].
    Only vinyl, US releases, sorted by want desc, de-duped by release_id.
    """
    decade_label = f"{decade_start}s"
    seen_ids: set[int] = set()
    candidates: List[TopSeller] = []

    print(f"== Collecting for decade {decade_label} (limit {limit}) ==")
    for year in range(decade_start, decade_start + 10):
        for page in range(1, max_pages_per_year + 1):
            if len(candidates) >= limit * 2:
                break

            results = client.search_year_page(year=year, page=page, per_page=per_page)
            if not results:
                # No more results for this year/page.
                break

            for r in results:
                rid = r.get("id")
                if not isinstance(rid, int):
                    continue
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)

                # Some results are not vinyl/US despite filters; double-check.
                country = (r.get("country") or "").upper()
                if country != "US":
                    continue

                formats = r.get("format") or []
                if not isinstance(formats, list):
                    formats = [formats]
                formats_lower = [str(f).lower() for f in formats]
                if "vinyl" not in formats_lower:
                    continue

                community = r.get("community") or {}
                want = int(community.get("want") or 0)
                have = int(community.get("have") or 0)
                rating = compute_rating(want, have)

                artist = str(r.get("artist") or "").strip()
                title = str(r.get("title") or "").strip()
                if not artist or not title:
                    continue

                # Use search year as fallback if 'year' field missing.
                ry = r.get("year")
                if isinstance(ry, int):
                    year_val = ry
                elif isinstance(ry, str) and ry.isdigit():
                    year_val = int(ry)
                else:
                    year_val = year

                candidates.append(
                    TopSeller(
                        release_id=rid,
                        year=year_val,
                        artist=artist,
                        title=title,
                        want=want,
                        have=have,
                        rating=rating,
                        decade_label=decade_label,
                    )
                )

        if len(candidates) >= limit * 2:
            break

    # Sort by rating desc, then want desc, then have desc.
    candidates.sort(
        key=lambda ts: (ts.rating, ts.want, ts.have),
        reverse=True,
    )

    # Trim to requested limit.
    return candidates[:limit]


def enrich_prices(client: DiscogsClient, sellers: List[TopSeller]) -> None:
    """
    For the final trimmed list for each decade, fetch price suggestions.
    """
    for ts in sellers:
        low, med, high = client.get_price_suggestions(ts.release_id)
        ts.low_price = low
        ts.med_price = med
        ts.high_price = high


# ---------------------- spreadsheet & txt writers ----------------------


def write_spreadsheet(
    out_path: Path,
    sellers: List[TopSeller],
) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        # Try to install on the fly (best-effort).
        import subprocess, sys

        print("openpyxl not found, attempting to install it...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
        from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "top_sellers"

    headers = [
        "order",
        "rating",          # 0–100
        "decade",
        "artist",
        "title",
        "discogs_id",
        "discogs_want",
        "discogs_have",
        "low_price",
        "med_price",
        "high_price",
    ]
    ws.append(headers)

    for idx, ts in enumerate(sellers, start=1):
        rating_pct = int(round(ts.rating * 100))
        row = [
            idx,
            rating_pct,
            ts.decade_label,
            ts.artist,
            ts.title,
            ts.release_id,
            ts.want,
            ts.have,
            ts.low_price,
            ts.med_price,
            ts.high_price,
        ]
        ws.append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out_path))
    print(f"  -> wrote spreadsheet: {out_path}")


def write_txt(out_path: Path, sellers: List[TopSeller]) -> None:
    """
    Optional compatibility export: plain text list "Artist / Title", ordered by rating.
    """
    lines = [f"{ts.artist} / {ts.title}" for ts in sellers]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> wrote txt: {out_path}")


# ---------------------- main ----------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build per-decade 'top sellers' spreadsheets using Discogs API.\n"
            "For each decade (1910–2020 by default) this script:\n"
            "  * searches Discogs for US vinyl releases sorted by want desc\n"
            "  * computes rating = want / (want + have)\n"
            "  * ranks items by rating and want\n"
            "  * fetches price suggestions (G+, VG+, NM/M-) for low/med/high\n"
            "  * writes an .xlsx and a .txt file in code/records/data_backups.\n"
        )
    )
    parser.add_argument(
        "--start-decade",
        type=int,
        default=1950,
        help="First decade to process (e.g. 1910, 1950). Default 1950.",
    )
    parser.add_argument(
        "--end-decade",
        type=int,
        default=2020,
        help="Last decade to process (inclusive). Default 2020.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Max number of records per decade (default 1000).",
    )
    parser.add_argument(
        "--discogs-delay",
        type=float,
        default=1.0,
        help="Base delay between API calls in seconds (default 1.0).",
    )
    parser.add_argument(
        "--no-txt",
        action="store_true",
        help="If set, do not emit companion .txt files (xlsx only).",
    )
    args = parser.parse_args()

    # Load env
    load_env_d_records()
    token = os.getenv("DISCOGS_TOKEN", "").strip()
    username = os.getenv("DISCOGS_USERNAME", "").strip()
    user_agent = (
        os.getenv("DISCOGS_USER_AGENT", "").strip()
        or "HuntTopSellers/1.0 +https://whitepup.github.io/store/"
    )
    if not token or not username:
        raise SystemExit("DISCOGS_TOKEN and DISCOGS_USERNAME must be set in D:\\records\\.env")

    # Paths
    script_path = Path(__file__).resolve()
    records_root = script_path.parents[2]  # ...\code\records
    data_backups_dir = records_root / "data_backups"
    data_backups_dir.mkdir(parents=True, exist_ok=True)

    print("Discogs env:")
    print(f"  username: {username}")
    print(f"  user-agent: {user_agent}")
    print(f"Using data_backups dir: {data_backups_dir}")
    print(f"Decades: {args.start_decade}–{args.end_decade}")
    print(f"Limit per decade: {args.limit}")
    print()

    client = DiscogsClient(
        token=token,
        username=username,
        user_agent=user_agent,
        delay=args.discogs_delay,
        cache_dir=Path("D:/records/outputs/hunt"),
    )

    for decade_start in range(args.start_decade, args.end_decade + 1, 10):
        decade_label = f"{decade_start}s"
        sellers = collect_for_decade(client, decade_start=decade_start, limit=args.limit)
        if not sellers:
            print(f"== No candidates for {decade_label}, skipping. ==")
            continue

        print(f"== Enriching prices for {decade_label} ({len(sellers)} items) ==")
        enrich_prices(client, sellers)

        count = len(sellers)
        xlsx_name = f"{decade_label}_top_sellers_{count}.xlsx"
        txt_name = f"{decade_label}_top_sellers_{count}.txt"

        xlsx_path = data_backups_dir / xlsx_name
        txt_path = data_backups_dir / txt_name

        write_spreadsheet(xlsx_path, sellers)
        if not args.no_txt:
            write_txt(txt_path, sellers)

    print("All done.")


if __name__ == "__main__":
    main()
