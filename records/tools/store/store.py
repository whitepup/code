#!/usr/bin/env python3
# store.py
# Discogs collection -> store_inventory.json + legacy index.html layout (unchanged)

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request
import urllib.error

API_BASE = "https://api.discogs.com"

# ---- legacy HTML layout (restored) ----
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
      img.style.cursor = "pointer";
      img.addEventListener("click", ()=>{ if(it.rid){ window.open(`https://www.discogs.com/release/${it.rid}`, "_blank"); } });

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

def build_items_from_discogs(releases: List[Dict[str, Any]], floor: float, token: str, user_agent: str, cache: Dict[str, Any], ttl_days: int) -> Tuple[List[dict], Dict[str,int]]:
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
        year = bi.get("year")
        try:
            year_i = int(year) if year not in (None, "") else None
        except Exception:
            year_i = None
        country = _norm(bi.get("country"))
        labels = bi.get("labels") or []
        label = _norm(labels[0].get("name")) if isinstance(labels, list) and labels else ""
        catno = _norm(labels[0].get("catno")) if isinstance(labels, list) and labels else ""
        formats = bi.get("formats") or []
        fmt = _norm(formats[0].get("name")) if isinstance(formats, list) and formats else ""
        img = _norm(bi.get("thumb") or bi.get("cover_image") or "")

        key = _make_key(artist, title)
        by_key_rids[key].append(rid_i)

        if key not in groups:
            groups[key] = {
                "key": key,
                "artist": artist,
                "title": title,
                "country": country,
                "label": label,
                "catno": catno,
                "format": fmt,
                "rid": str(rid_i),
                "img": img,
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
    title = env("STORE_TITLE", "Record Store") or "Record Store"
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

    print("=== Store Builder (Legacy Layout + Discogs prices) ===", flush=True)
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
    items, price_stats = build_items_from_discogs(releases, floor, token, user_agent, cache, ttl_days)
    save_cache(CACHE_PATH, cache)

    inv_path = SITE_DIR / "store_inventory.json"
    inv_path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {inv_path}", flush=True)

    html_path = SITE_DIR / "index.html"
    html_out = HTML.replace("<title>Record Store</title>", f"<title>{title}</title>")
    html_out = html_out.replace(">Record Store<", f">{title}<")
    html_path.write_text(html_out, encoding="utf-8")
    print(f"Site: {html_path}", flush=True)

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
