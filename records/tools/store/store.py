#!/usr/bin/env python3
# BUILD_ID: 20260113_STORE_V12

from __future__ import annotations

import csv
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Runtime roots
RECORDS_HOME = Path(os.getenv("RECORDS_HOME", r"D:\records"))
ENV_PATH = RECORDS_HOME / ".env"
load_dotenv(ENV_PATH, override=True)

RECORDS_OUT = Path(os.getenv("RECORDS_OUT", r"D:\records\outputs"))

OFFLINE_OUT = RECORDS_OUT / "offline_gallery"
SITE_DIR = RECORDS_OUT / "store" / "site"

# Persistent (hand-edited) pricing overrides
DATA_DIR = RECORDS_HOME / "data" / "store"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PRICE_FILE = DATA_DIR / "pricing_overrides.csv"


def _safe_int_year(y: str) -> Optional[int]:
    s = (y or "").strip()
    if not s:
        return None
    s = re.sub(r"\.0$", "", s)  # handle Excel 1961.0
    if not s.isdigit():
        return None
    v = int(s)
    if v < 1800 or v > 2100:
        return None
    return v


def _decade(y: Optional[int]) -> str:
    if not y:
        return "Unknown"
    return f"{(y // 10) * 10}s"


def _norm(s: str) -> str:
    return (s or "").strip()


def _key_artist_title(artist: str, title: str) -> str:
    def norm2(x: str) -> str:
        x = (x or "").strip().lower()
        x = re.sub(r"\s+", " ", x)
        return x
    return norm2(artist) + "||" + norm2(title)


def _choose_year(years: List[Optional[int]]) -> Optional[int]:
    ys = [y for y in years if isinstance(y, int)]
    return min(ys) if ys else None


def load_pricing_overrides(path: Path) -> Dict[str, dict]:
    r"""
    pricing_overrides.csv lives in D:\records\data\store\pricing_overrides.csv (persistent).
    Keyed by normalized artist||title.
    """
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


def discover_records_csv_files(root: Path) -> List[Path]:
    """Return all records.csv files under offline_gallery output.

    Supports both legacy layout:
      offline_gallery/records.csv
    and newer layouts where each tab/folder is written under a subfolder:
      offline_gallery/<tab>/records.csv
    """
    files: List[Path] = []
    root = Path(root)
    p0 = root / "records.csv"
    if p0.exists():
        files.append(p0)
    for p in root.rglob("records.csv"):
        if p not in files:
            files.append(p)
    return files


def read_records_csv_dedup(paths, pricing: Dict[str, dict]) -> List[dict]:
    """
    Reads one or more offline_gallery records.csv files and returns *deduped* store items grouped by Artist+Title.
    Applies pricing overrides by key.
    """
    if isinstance(paths, (str, Path)):
        paths = [Path(paths)]
    paths = [Path(p) for p in (paths or []) if Path(p).exists()]
    if not paths:
        raise FileNotFoundError(f"Missing records.csv under: {OFFLINE_OUT}")

    groups: Dict[str, dict] = {}
    years_by_key: Dict[str, List[Optional[int]]] = defaultdict(list)
    high_sold_by_key: Dict[str, List[Optional[float]]] = defaultdict(list)
    seen_rids: set[str] = set()

    for path in paths:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                folder = _norm(row.get("folder", ""))
                # Include all "For Sale*" folders (LPs, 7\", 10\", 78s, etc.)
                if not folder.lower().startswith("for sale"):
                    continue

                rid = _norm(row.get("release_id", ""))
                if not rid:
                    continue
                if rid in seen_rids:
                    continue
                seen_rids.add(rid)

                artist = _norm(row.get("artist", ""))
                title = _norm(row.get("title", ""))
                if not artist and not title:
                    continue

                key = _key_artist_title(artist, title)

                year_raw = _norm(row.get("year", ""))
                y = _safe_int_year(year_raw)
                years_by_key[key].append(y)

                # Discogs high sold value (may be absent depending on offline_gallery version)
                high_sold = None
                for col in (
                    "high_sold_value",
                    "sold_high",
                    "high_sold",
                    "sold_value_high",
                    "discogs_high_sold_value",
                    "highest_sold",
                    "high_sold_usd",
                ):
                    if col in row and _norm(row.get(col, "")):
                        try:
                            high_sold = float(re.sub(r"[^0-9.\-]", "", _norm(row.get(col, ""))))
                        except Exception:
                            high_sold = None
                        if high_sold is not None:
                            break
                high_sold_by_key[key].append(high_sold)

                country = _norm(row.get("country", ""))
                label = _norm(row.get("label", ""))
                catno = _norm(row.get("catno", ""))
                fmt = _norm(row.get("format", ""))
                img = _norm(row.get("cover_image", "")) or _norm(row.get("image", "")) or _norm(row.get("img", ""))

                # Only keep one representative row per key (dedup)
                if key not in groups:
                    groups[key] = {
                        "key": key,
                        "artist": artist,
                        "title": title,
                        "country": country,
                        "label": label,
                        "catno": catno,
                        "format": fmt,
                        "rid": rid,
                        "img": img,
                        "price": "",
                        "status": "",
                        "condition": "",
                        "sleeve_condition": "",
                        "notes": "",
                    }

    # Apply pricing overrides + defaults
    items: List[dict] = []
    for key, g in groups.items():
        ov = pricing.get(key)
        if ov:
            if _norm(ov.get("price", "")):
                g["price"] = _norm(ov.get("price", ""))
            if _norm(ov.get("status", "")):
                g["status"] = _norm(ov.get("status", ""))
            if _norm(ov.get("condition", "")):
                g["condition"] = _norm(ov.get("condition", ""))
            if _norm(ov.get("sleeve_condition", "")):
                g["sleeve_condition"] = _norm(ov.get("sleeve_condition", ""))
            if _norm(ov.get("notes", "")):
                g["notes"] = _norm(ov.get("notes", ""))

        # If no override price: use Discogs high sold value, floor $4, round to nearest $.
        # If no sold value available, default to $9.
        if not _norm(str(g.get("price", ""))):
            vals = [v for v in high_sold_by_key.get(key, []) if isinstance(v, float) and v > 0]
            if vals:
                p = int(round(max(vals)))
                if p < 4:
                    p = 4
                g["price"] = str(p)
            else:
                g["price"] = "9"

        chosen = _choose_year(years_by_key.get(key, []))
        if chosen is not None:
            g["year"] = str(chosen)
            g["decade"] = _decade(chosen)
        else:
            g["decade"] = "Unknown"

        if g.get("img"):
            g["img"] = g["img"].lstrip("/\\")

        items.append(g)

    items.sort(key=lambda x: ((x.get("artist") or "").lower(), (x.get("title") or "").lower()))
    return items


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Record Store</title>
  <style>
    html, body { margin: 0; padding: 0; height: 100%; } body { font-family: Arial, sans-serif; background: #fff; color: #111; display: flex; flex-direction: column; }
    .header { position: sticky; top: 0; z-index: 50; background: #fff; border-bottom: 1px solid #e6e6e6; padding: 12px 14px; }
    .top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .title { font-size: 20px; font-weight: 800; margin-right: 8px; }
    .sub { font-size: 12px; color: #666; margin-top: 6px; }
    .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; width: 100%; margin-top: 10px; }
    input, select { border: 1px solid #d6d6d6; border-radius: 10px; padding: 8px 10px; background: #fff; }
    input { flex: 1; min-width: 220px; }
    .btn { border: 1px solid #d6d6d6; background: #fff; padding: 8px 10px; border-radius: 10px; cursor: pointer; }
    .btn:disabled { opacity: .45; cursor: not-allowed; }
    .cartbtn { margin-left: auto; white-space: nowrap; }
    .content { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 14px; }
    .grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 6px; }
    .card { border: 1px solid #eee; border-radius: 10px; padding: 6px 8px; display: flex; align-items: center; gap: 8px; }
    .cover { width: 64px; height: 64px; border-radius: 8px; object-fit: cover; background: #f5f5f5; flex: 0 0 auto; }
    .meta { flex: 1 1 auto; min-width: 0; }
    .artist { font-weight: 800; }
    .title2 { margin-top: 2px; }
    .yearline { margin-top: 2px; font-size: 12px; color: #666; }
    .line { margin-top: 6px; font-size: 12px; color: #333; }
    .muted { color: #666; }
    .row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-top: 4px; }
    .price { font-weight: 900; }
    .badge { font-size: 12px; padding: 4px 8px; border-radius: 999px; border: 1px solid #ddd; background: #fafafa; }
    .badge.pending { background: #fff4b8; border-color: #e5d27a; }
    .badge.sold { background: #eee; }
    .badge.hold { background: #e6f3ff; }
    .small { font-size: 12px; }
    .modal { position: fixed; inset: 0; background: rgba(0,0,0,.55); display: none; align-items: center; justify-content: center; padding: 18px; }
    .modal.open { display: flex; }
    .modalbox { width: min(720px, 96vw); max-height: 90vh; overflow: auto; background: #fff; border-radius: 16px; padding: 14px; }
    .modalhead { display: flex; align-items: center; gap: 10px; }
    .modalhead h2 { margin: 0; font-size: 18px; }
    .close { margin-left: auto; }
    textarea { width: 100%; min-height: 220px; border-radius: 12px; border: 1px solid #d6d6d6; padding: 10px; }
    .nowrap { white-space: nowrap; }
    .qtypill{font-size:12px;padding:3px 7px;border-radius:999px;border:1px solid #ddd;background:#fff}
  
    .intro { margin: 10px 0 16px; padding: 10px 12px; border: 1px solid #ddd; border-radius: 10px; background: rgba(0,0,0,0.02); }
    .intro p { margin: 6px 0; }
    .cartlist { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
    .cartrow { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid #ddd; border-radius: 10px; }
    .cartrow .meta { flex: 1; }
    .cartrow .qty { font-variant-numeric: tabular-nums; min-width: 64px; text-align: right; }
    .cartrow button { padding: 6px 10px; }

  /* V11 modal fixes */
#modal { z-index: 99999 !important; }
#modal .modal-card { max-width: min(980px, calc(100vw - 24px)); width: min(980px, calc(100vw - 24px)); overflow-x: hidden; }
#modal .modal-body { overflow-x: hidden; }
#cartList { overflow-x: hidden; }
.cartrow { flex-wrap: wrap; overflow-x: hidden; }
.cartrow .meta { min-width: 0; overflow-wrap: anywhere; word-break: break-word; }
#cartText { overflow-x: hidden; white-space: pre-wrap; }

  
    .pricecol { min-width: 56px; text-align: center; font-weight: 900; font-size: 13px; }
    .controlsRow { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 40px; }
    .controlsRow .btn { padding: 3px 5px; font-size: 11px; }
    .controlsRow .small { font-size: 11px; }
</style>
</head>
<body>
  <div class="header">
    <div class="controls">
      <button id="helpOpen" class="btn">Help / About</button>
      <button id="cartOpen" class="btn cartbtn">Cart (0)</button>
      <input id="q" placeholder="Search artist or title..." />
      <select id="artist"><option value="">All artists</option></select>
      <select id="genre"><option value="">All genres</option></select>
      <select id="decade"><option value="">All decades</option></select>
      <button id="clear" class="btn">Clear</button>
    </div>
  </div>

  <div class="content">
    <div id="status" class="muted small">Loading…</div>
    <div id="grid" class="grid" style="margin-top:10px;"></div>
  </div>

  <div id="modal" class="modal" aria-hidden="true">
    <div class="modalbox">
      <div class="modalhead">
        <h2>Your cart</h2>
        <button id="modalClose" class="btn close">Close</button>
      </div>
      <div class="muted small" style="margin-top:6px;">Copy/paste this into a message to me.</div>
      <textarea id="cartText" readonly></textarea>
      <div id="cartList" class="cartlist"></div>
      <div class="row">
        <button id="clearCartBtn" class="btn">Clear cart</button>
        <button id="copyBtn" class="btn">Copy</button>
<div id="cartMeta" class="muted small"></div>
      </div>
    </div>
  </div>

<script>
document.addEventListener("DOMContentLoaded", function(){
(function(){
  const $ = (id)=>document.getElementById(id);
  const state = { items: [], filtered: [], cart: {} };
  const CART_KEY = "store_cart_v1";

  function loadCart(){ try{ state.cart = JSON.parse(localStorage.getItem(CART_KEY)||"{}")||{}; }catch{ state.cart={}; } }
  function saveCart(){ localStorage.setItem(CART_KEY, JSON.stringify(state.cart)); }

  function money(x){
    const n = Number(String(x||"").replace(/[^0-9.]/g,""));
    return isFinite(n) && n>0 ? "$" + n.toFixed(0) : "";
  }

  function cartSummary(){
    const lines = [];
    const cartItems = [];
    let total = 0, count = 0;
    lines.push("Record order inquiry:");
    lines.push("");
    Object.keys(state.cart).sort().forEach(rid=>{
      const qty = state.cart[rid]||0;
      if(qty<=0) return;
      const it = state.items.find(x=>x.release_id===rid);
      if(!it) return;
      const p = Number(String(it.price||"").replace(/[^0-9.]/g,""));
      const linePrice = (isFinite(p)&&p>0) ? p*qty : 0;
      if(linePrice) total += linePrice;
      count += qty;
      lines.push(`${qty}x ${it.artist} — ${it.title} (${it.year || "?"}) [${rid}] ${money(it.price) || ""}`.trim());
      if(it.status && it.status!=="available") lines.push(`   Status: ${it.status}`);
      if(it.condition) lines.push(`   Condition: ${it.condition}`);
      if(it.notes) lines.push(`   Notes: ${it.notes}`);
      if(it.qty>1) lines.push(`   Copies/Variants in stock: ${it.qty}`);
    });
    lines.push("");
    lines.push(`Items: ${count}`);
    if(total>0) lines.push(`Total: $${total.toFixed(0)}`);
    lines.push("");
    lines.push("Name:");
    lines.push("Pickup or Shipping (zip):");
    lines.push("Payment preference:");
    return { text: lines.join("\\n"), total, count };
  }

  
function renderCartList(cartItems){
  const el = $("cartList");
  if(!el) return;
  if(!cartItems || cartItems.length===0){
    el.innerHTML = `<div class="muted small">Cart is empty.</div>`;
    return;
  }
  el.innerHTML = cartItems.map(ci=>{
    const label = `${ci.artist} — ${ci.title} (${ci.year}) [${ci.rid}]`;
    return `
      <div class="cartrow">
        <div class="meta">${escapeHtml(label)}</div>
        <div class="qty">Qty: <b>${ci.qty}</b></div>
        <button class="btn" data-action="remove-one" data-rid="${ci.rid}">-1</button>
        <button class="btn" data-action="add-one" data-rid="${ci.rid}">+1</button>
        <button class="btn" data-action="remove-all" data-rid="${ci.rid}">Remove</button>
      </div>`;
  }).join("");

  el.querySelectorAll("button[data-action]").forEach(btn=>{
    btn.addEventListener("click", ()=>{
      const rid = btn.getAttribute("data-rid");
      const act = btn.getAttribute("data-action");
      const cur = Number(state.cart[rid]||0);
      if(act==="remove-one"){
        const next = Math.max(0, cur-1);
        if(next===0) delete state.cart[rid]; else state.cart[rid]=next;
      }else if(act==="add-one"){
        state.cart[rid] = cur+1;
      }else if(act==="remove-all"){
        delete state.cart[rid];
      }
      saveCart(); updateCartButton(); openCart(); // re-render modal
    });
  });
}

function updateCartButton(){
    const {count, total} = cartSummary();
    $("cartOpen").textContent = total>0 ? `Cart (${count}) — $${total.toFixed(0)}` : `Cart (${count})`;
  }

  function badge(status){
    const s = (status||"available").toLowerCase();
    if(s==="pending") return `<span class="badge pending">Pending</span>`;
    if(s==="sold") return `<span class="badge sold">Sold</span>`;
    if(s==="hold") return `<span class="badge hold">Hold</span>`;
    return "";
  }

  const HIDE_PENDING = true;
  function isHiddenByStatus(it){
    const hide = HIDE_PENDING;
    if(!hide) return false;
    const s = (it.status||"available").toLowerCase();
    return (s==="pending" || s==="sold");
  }

  function applyFilters(){
    const q = ($("q").value||"").trim().toLowerCase();
    const a = $("artist").value;
    const g = $("genre").value;
    const d = $("decade").value;

    state.filtered = state.items.filter(it=>{
      if(isHiddenByStatus(it)) return false;
      if(q && !(it.search_blob||"").includes(q)) return false;
      if(a && it.artist !== a) return false;
      if(g && (it.genre||"Unknown") !== g) return false;
      if(d && (it.decade||"Unknown") !== d) return false;
      return true;
    });

    render();
  }

  function setFilterOptions(){
    const artists = [...new Set(state.items.map(x=>x.artist).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    const genres  = [...new Set(state.items.map(x=>x.genre||"Unknown"))].sort((a,b)=>a.localeCompare(b));
    const decades = [...new Set(state.items.map(x=>x.decade||"Unknown"))].sort((a,b)=>a.localeCompare(b));

    function fill(sel, label, arr){
      const cur = sel.value;
      sel.innerHTML = `<option value="">${label}</option>`;
      arr.forEach(v=>{
        const o = document.createElement("option");
        o.value=v; o.textContent=v;
        sel.appendChild(o);
      });
      if(arr.includes(cur)) sel.value = cur;
    }
    fill($("artist"), "All artists", artists);
    fill($("genre"), "All genres", genres);
    fill($("decade"), "All decades", decades);
  }

  function render(){
    $("status").textContent = `${state.filtered.length} shown / ${state.items.length} total`;
    const grid = $("grid");
    grid.innerHTML = "";
    state.filtered.forEach(it=>{
      const inCart = state.cart[it.release_id] ? 1 : 0;

      const card = document.createElement("div");
      card.className = "card";

      // Price on far left
      const priceCol = document.createElement("div");
      priceCol.className = "pricecol";
      const priceText = money(it.price);
      priceCol.textContent = priceText || "";

      // Vertical controls column next: +, -, ? buttons
      const controls = document.createElement("div");
      controls.className = "controlsRow";

      function makeIconBtn(svg, label){
        const b = document.createElement("button");
        b.className = "btn iconbtn";
        b.setAttribute("aria-label", label);
        b.innerHTML = svg;
        return b;
      }

      const plusSvg = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>';
      const minusSvg = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M5 12h14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>';
      const qSvg = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M9.5 9a3 3 0 1 1 4.2 2.7c-.9.4-1.2.8-1.2 1.8v.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 18h.01" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/></svg>';

      const plus = makeIconBtn(plusSvg, "Add");
      plus.disabled = inCart > 0;
      plus.onclick = ()=>{
        if(state.cart[it.release_id]) return;
        state.cart[it.release_id] = 1;
        saveCart(); updateCartButton(); render();
      };

      const minus = makeIconBtn(minusSvg, "Remove");
      minus.disabled = inCart <= 0;
      minus.onclick = ()=>{
        if(!state.cart[it.release_id]) return;
        delete state.cart[it.release_id];
        saveCart(); updateCartButton(); render();
      };

      const infoBtn = makeIconBtn(qSvg, "Details");
      infoBtn.onclick = ()=>openItemModal(it);

      // + above -
      controls.appendChild(plus);
      controls.appendChild(minus);
      controls.appendChild(infoBtn);

      // Image next
      const img = document.createElement("img");
      img.className = "cover";
      img.loading = "lazy";
      img.src = it.img || "";
      img.alt = `${it.artist || ""} — ${it.title || ""}`.trim();
      img.onerror = ()=>{ img.style.visibility="hidden"; };

      // Title + artist stacked vertically to the right
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.innerHTML = `
        <div class="artist">${escapeHtml(it.artist || "")}</div>
        <div class="title2">${escapeHtml(it.title || "")}</div>
            <div class="yearline">${it.year ? escapeHtml(it.year) : ""}</div>
      `;

      card.appendChild(priceCol);
      card.appendChild(controls);
      card.appendChild(img);
      card.appendChild(meta);

      grid.appendChild(card);
    });
    setFilterOptions();

  }

  function escapeHtml(s){
    return String(s||"")
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;")
      .replaceAll("'","&#39;");
  }


  function openItemModal(it){
    const modal = $("itemModal");
    if(!modal) return;
    const titleEl = $("itemModalTitle");
    const bodyEl = $("itemModalBody");
    if(titleEl){
      titleEl.textContent = [it.artist || "", it.title || ""].filter(Boolean).join(" — ");
    }
    if(bodyEl){
      const year = it.year || "?";
      const label = it.label || "";
      const catno = it.catno || "";
      const genre = it.genre || "";
      bodyEl.innerHTML = `
        <p><b>Year:</b> ${escapeHtml(year)}</p>
        <p><b>Label:</b> ${escapeHtml(label)}</p>
        <p><b>Catalog #:</b> ${escapeHtml(catno)}</p>
        <p><b>Genre:</b> ${escapeHtml(genre)}</p>
      `;
    }
    modal.style.display = "flex";
    modal.classList.add("open");
    modal.setAttribute("aria-hidden","false");
  }

  function closeItemModal(){
    const modal = $("itemModal");
    if(!modal) return;
    modal.style.display = "none";
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden","true");
  }

  function openCart(){
    const {text, total, count, cartItems} = cartSummary();
    $("cartText").value = text;
    $("cartMeta").textContent = total>0 ? `Items: ${count}  •  Total: $${total.toFixed(0)}` : `Items: ${count}`;
    
    renderCartList(cartItems);
$("modal").classList.add("open");
    $("modal").setAttribute("aria-hidden","false");
  }
  function closeCart(){
    $("modal").classList.remove("open");
    $("modal").setAttribute("aria-hidden","true");
  }

  function boot(){
    loadCart();
    updateCartButton();

    const itemClose = $("itemModalClose");
    if(itemClose){ itemClose.addEventListener("click", closeItemModal); }

$("q").addEventListener("input", ()=>applyFilters());
    $("artist").addEventListener("change", ()=>applyFilters());
    $("genre").addEventListener("change", ()=>applyFilters());
    $("decade").addEventListener("change", ()=>applyFilters());
    $("clear").addEventListener("click", ()=>{
      $("q").value="";
      $("artist").value="";
      $("genre").value="";
      $("decade").value="";
      applyFilters();
    });

    $("cartOpen").addEventListener("click", openCart);
    $("modalClose").addEventListener("click", closeCart);
    $("modal").addEventListener("click", (e)=>{ if(e.target===$("modal")) closeCart(); });

    // Item modal close (backdrop + Esc)
    const im = $("itemModal");
    if(im){ im.addEventListener("click", (e)=>{ if(e.target===im) closeItemModal(); }); }
    document.addEventListener("keydown", (e)=>{ if(e.key==="Escape"){ closeCart(); closeItemModal(); } });

    $("copyBtn").addEventListener("click", async ()=>{
      try{
        await navigator.clipboard.writeText($("cartText").value);
        $("copyBtn").textContent="Copied!";
      }catch(e){
        $("copyBtn").textContent="Copy failed";
      }
      setTimeout(()=>$("copyBtn").textContent="Copy", 1200);
    });

    $("clearCartBtn").addEventListener("click", ()=>{
      state.cart = {};
      saveCart(); updateCartButton(); openCart();
    });

    fetch("store_inventory.json", {cache:"no-store"})
      .then(r=>{
        if(!r.ok) throw new Error("HTTP "+r.status);
        return r.json();
      })
      .then(j=>{
        state.items = (j && j.items) ? j.items : [];
        state.filtered = state.items.slice();
        applyFilters();
      })
      .catch(err=>{
        $("status").textContent = "Failed to load store_inventory.json: " + err;
        console.error(err);
      });
  }
  boot();
})();
});
</script>


<div id="itemModal" class="modal" aria-hidden="true" style="display:none">
  <div class="modalbox">
    <div class="modalhead">
      <h2 id="itemModalTitle">Record details</h2>
      <button id="itemModalClose" class="btn close">Close</button>
    </div>
    <div class="modal-body small" id="itemModalBody" style="overflow-y:auto;max-height:70vh;"></div>
  </div>
</div>

<div id="helpModal" class="modal" aria-hidden="true" style="display:none">
  <div class="modalbox">
    <div class="modalhead">
      <h2>About This Catalog</h2>
      <button id="helpClose" class="btn close">Close</button>
    </div>
    <div class="modal-body small" style="overflow-y:auto;max-height:70vh;">
      <p><b>Collection focus:</b> Classic pop, jazz, easy listening, and vocal LPs.</p>
      <p><b>How to use:</b> Browse, use search and filters, then tap <b>Add to Cart</b> on anything you’re interested in.</p>
      <p>The cart builds a simple text list you can <b>copy/paste into a Facebook Marketplace message</b> when you’re ready to reach out.</p>
      <p><b>If records is not in very good condition a discount will be applied</b></p>
      <p>Feel free to message for detailed grading or questions — happy to help.</p>
    </div>
  </div>
</div>

<script>
(function(){
  const hm = document.getElementById("helpModal");
  const open = document.getElementById("helpOpen");
  const close = document.getElementById("helpClose");
  if(open){ open.onclick = ()=>{ hm.style.display='flex'; hm.classList.add('open'); hm.setAttribute('aria-hidden','false'); }; }
  if(close){ close.onclick = ()=>{ hm.style.display='none'; hm.classList.remove('open'); hm.setAttribute('aria-hidden','true'); }; }
})();
</script>

</body>
</html>
"""


def main() -> int:
    print("=== Store Builder ===", flush=True)
    print(f"Offline gallery: {OFFLINE_OUT}", flush=True)
    print(f"Site output: {SITE_DIR}", flush=True)
    print(f"Pricing overrides: {PRICE_FILE}", flush=True)

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "images").mkdir(parents=True, exist_ok=True)

    records_csv_files = discover_records_csv_files(OFFLINE_OUT)
    pricing = load_pricing_overrides(PRICE_FILE)
    items = read_records_csv_dedup(records_csv_files, pricing)

    inv_path = SITE_DIR / "store_inventory.json"
    inv_path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {inv_path}", flush=True)

    # Copy images referenced by items to site/images and rewrite img to relative paths
    src_images = OFFLINE_OUT / "images"
    dst_images = SITE_DIR / "images"
    copied = 0
    for it in items:
        rel = (it.get("img") or "").strip()
        if not rel:
            continue
        name = rel.split("/")[-1].split("\\")[-1]
        src = src_images / name
        dst = dst_images / name
        if src.exists():
            shutil.copy2(src, dst)
            copied += 1
            it["img"] = f"images/{name}"

    # Rewrite inventory after img normalization
    inv_path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Images ready: {dst_images} (copied {copied})", flush=True)

    html_path = SITE_DIR / "index.html"
    html_path.write_text(HTML, encoding="utf-8", newline="\n")
    print(f"Site: {html_path}", flush=True)
    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())