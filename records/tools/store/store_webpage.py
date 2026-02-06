#!/usr/bin/env python3
# store_webpage.py
# Build static store webpage (index.html) from existing store_inventory.json without Discogs API access.

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

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


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return v


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Record Store</title>
  <style>
    :root{ --header-h: 0px; }
    html, body { margin: 0; padding: 0; height: 100%; }
    body { font-family: Arial, sans-serif; background: #fff; color: #111; }

    /* Sticky control bar (no page title) */
    .header { position: fixed; top: 0; left: 0; right: 0; z-index: 2000; background: #fff; border-bottom: 1px solid #e6e6e6; padding: 12px 14px; }
    .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; width: 100%; }
    input, select { border: 1px solid #d6d6d6; border-radius: 10px; padding: 8px 10px; background: #fff; }
    input { flex: 1; min-width: 220px; }
    .btn { border: 1px solid #d6d6d6; background: #fff; padding: 8px 10px; border-radius: 10px; cursor: pointer; }
    .btn:disabled { opacity: .45; cursor: not-allowed; }
    .cartbtn { margin-left: auto; white-space: nowrap; }

    .wrap { padding: 12px 14px 24px; }
    .status { font-size: 12px; color: #666; margin: 8px 0; }

    table { border-collapse: collapse; width: 100%; }
    th, td { border-bottom: 1px solid #eee; padding: 8px 10px; text-align: left; vertical-align: middle; }
    th { position: sticky; top: var(--header-h); background: #fafafa; z-index: 10; user-select: none; cursor: pointer; }
    th.noclick { cursor: default; }
    .nowrap { white-space: nowrap; }

    /* cover thumbs */
    .thumb { width: 64px; height: 64px; object-fit: cover; border-radius: 6px; background: #f5f5f5; display: block; }
    a.dlink { color: inherit; text-decoration: none; }
    a.dlink:hover { text-decoration: underline; }

    /* +/- controls: vertical stack, no count */
    .iconstack { display: flex; flex-direction: column; gap: 4px; align-items: center; justify-content: center; }
    .iconbtn { border: 1px solid #d6d6d6; background: #fff; border-radius: 10px; width: 28px; height: 28px; cursor: pointer; font-weight: 900; line-height: 1; }
    .iconbtn:disabled { opacity: .45; cursor: not-allowed; }

    /* hover preview (offline_gallery style) */
    #imgHoverOverlay { position: fixed; z-index: 9999; display: none; pointer-events: none; background: #fff; border: 1px solid #ddd; border-radius: 12px; padding: 8px; box-shadow: 0 8px 30px rgba(0,0,0,.15); }
    #imgHoverOverlay img { max-width: min(820px, 90vw); max-height: min(820px, 90vh); display: block; border-radius: 10px; }

    /* cart / help modals (legacy) */
    .modal { position: fixed; inset: 0; background: rgba(0,0,0,.55); display: none; align-items: center; justify-content: center; padding: 18px; }
    .modal.open { display: flex; }
    .modalbox { width: min(720px, 96vw); max-height: 90vh; overflow: auto; background: #fff; border-radius: 16px; padding: 14px; }
    .modalhead { display: flex; align-items: center; gap: 10px; }
    .modalhead h2 { margin: 0; font-size: 18px; }
    .close { margin-left: auto; }
    textarea { width: 100%; min-height: 220px; border-radius: 12px; border: 1px solid #d6d6d6; padding: 10px; }
    .row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-top: 8px; }
    .small { font-size: 12px; }
    .muted { color: #666; }

    .cartlist { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
    .cartrow { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid #ddd; border-radius: 10px; flex-wrap: wrap; }
    .cartrow .meta { flex: 1; min-width: 0; overflow-wrap: anywhere; word-break: break-word; }

    /* highlight rows in cart */
    tr.incart td { background: rgba(255, 244, 184, 0.45); }
  </style>
</head>
<body>
  <div class="header" id="header">
    <div class="controls">
      <button id="helpOpen" class="btn" type="button">Help / About</button>
      <button id="cartOpen" class="btn cartbtn" type="button">Cart (0)</button>
      <input id="q" placeholder="Search artist or title..." />
      <select id="artist"><option value="">All artists</option></select>
      <select id="genre"><option value="">All genres</option></select>
      <select id="decade"><option value="">All decades</option></select>
      <button id="clear" class="btn" type="button">Clear</button>
    </div>
  </div>

  <div class="wrap">
    <div id="status" class="status">Loading…</div>
    <table id="tbl" aria-label="Store inventory" style="display:none">
      <thead>
        <tr>
          <th class="nowrap">price</th>
          <th class="nowrap noclick">+ / −</th>
          <th class="nowrap noclick">cover</th>
          <th>artist</th>
          <th>title</th>
          <th class="nowrap">year</th>
          <th class="nowrap">format</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>

  <!-- Cart modal -->
  <div id="modal" class="modal" aria-hidden="true">
    <div class="modalbox">
      <div class="modalhead">
        <h2>Your cart</h2>
        <button id="modalClose" class="btn close" type="button">Close</button>
      </div>
      <div class="muted small" style="margin-top:6px;">Copy/paste this into a message to me.</div>
      <textarea id="cartText" readonly></textarea>
      <div id="cartList" class="cartlist"></div>
      <div class="row">
        <button id="clearCartBtn" class="btn" type="button">Clear cart</button>
        <button id="copyBtn" class="btn" type="button">Copy</button>
        <div id="cartMeta" class="muted small"></div>
      </div>
    </div>
  </div>

  <!-- Help / About modal -->
  <div id="helpModal" class="modal" aria-hidden="true">
    <div class="modalbox">
      <div class="modalhead">
        <h2>About This Catalog</h2>
        <button id="helpClose" class="btn close" type="button">Close</button>
      </div>
      <div class="modal-body small" style="overflow-y:auto;max-height:70vh;">
        <p><b>Collection focus:</b> Classic pop, jazz, easy listening, and vocal LPs.</p>
        <p><b>How to use:</b> Browse, use search and filters, then tap <b>+</b> on anything you’re interested in.</p>
        <p>The cart builds a simple text list you can <b>copy/paste into a Facebook Marketplace message</b> when you’re ready to reach out.</p>
        <p><b>If records is not in very good condition a discount will be applied</b></p>
        <p>Feel free to message for detailed grading or questions — happy to help.</p>
      </div>
    </div>
  </div>

  <script>
  (function(){
    const $ = (id)=>document.getElementById(id);

    const state = { items: [], filtered: [], cart: {} };
    const CART_KEY = "store_cart_v1";

    function loadCart(){ try{ state.cart = JSON.parse(localStorage.getItem(CART_KEY)||"{}")||{}; }catch{ state.cart={}; } }
    function saveCart(){ try{ localStorage.setItem(CART_KEY, JSON.stringify(state.cart||{})); }catch(e){} }

    function money(x){
      const n = Number(String(x||"").replace(/[^0-9.]/g,""));
      return isFinite(n) && n>0 ? "$" + n.toFixed(0) : "";
    }

    function ridOf(it){ return String(it.release_id || it.rid || it.id || it.key || ""); }

    function computeYear(it){
      const y = it.year ?? it.released ?? it.release_year ?? "";
      const n = Number(String(y).replace(/[^0-9]/g,""));
      return Number.isFinite(n) && n>0 ? String(n) : "";
    }

    function computeDecade(it){
      const y = Number(computeYear(it));
      if(Number.isFinite(y) && y>0){
        const d = Math.floor(y/10)*10;
        return String(d) + "s";
      }
      return "Unknown";
    }

    function computeGenre(it){
      const g = it.genre || it.genres || it.style || it.styles || "";
      if(Array.isArray(g)) return (g[0] ? String(g[0]) : "Unknown");
      const s = String(g||"").trim();
      return s ? s : "Unknown";
    }

    function searchBlob(it){
      const parts = [
        it.artist, it.title, it.label, it.catno, it.format,
        computeYear(it), computeGenre(it), computeDecade(it),
      ].filter(Boolean).map(x=>String(x).toLowerCase());
      return parts.join(" ");
    }

    function escapeHtml(s){
      return String(s||"")
        .replaceAll("&","&amp;")
        .replaceAll("<","&lt;")
        .replaceAll(">","&gt;")
        .replaceAll('"',"&quot;")
        .replaceAll("'","&#39;");
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
        const it = state.items.find(x=>ridOf(x)===rid);
        if(!it) return;

        const p = Number(String(it.price||"").replace(/[^0-9.]/g,""));
        const linePrice = (isFinite(p)&&p>0) ? p*qty : 0;
        if(linePrice) total += linePrice;
        count += qty;

        const year = computeYear(it) || "?";
        lines.push(`${qty}x ${it.artist} — ${it.title} (${year}) [${rid}] ${money(it.price) || ""}`.trim());
        if(it.status && String(it.status).toLowerCase()!=="available") lines.push(`   Status: ${it.status}`);
        if(it.condition) lines.push(`   Condition: ${it.condition}`);
        if(it.notes) lines.push(`   Notes: ${it.notes}`);
        if(it.qty && Number(it.qty)>1) lines.push(`   Copies/Variants in stock: ${it.qty}`);

        cartItems.push({ rid, qty, artist: it.artist||"", title: it.title||"", year: year });
      });

      lines.push("");
      lines.push(`Items: ${count}`);
      if(total>0) lines.push(`Total: $${total.toFixed(0)}`);
      lines.push("");
      lines.push("Name:");
      lines.push("Pickup or Shipping (zip):");
      lines.push("Payment preference:");

      return { text: lines.join("\\n"), total, count, cartItems };
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
            <button class="btn" data-action="remove" data-rid="${escapeHtml(ci.rid)}">Remove</button>
          </div>`;
      }).join("");

      el.querySelectorAll("button[data-action]").forEach(btn=>{
        btn.addEventListener("click", ()=>{
          const rid = btn.getAttribute("data-rid");
          delete state.cart[rid];
          saveCart(); updateCartButton(); render();
          openCart(); // refresh modal contents
        });
      });
    }

    function updateCartButton(){
      const {count, total} = cartSummary();
      $("cartOpen").textContent = total>0 ? `Cart (${count}) — $${total.toFixed(0)}` : `Cart (${count})`;
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

    function openHelp(){
      $("helpModal").classList.add("open");
      $("helpModal").setAttribute("aria-hidden","false");
    }
    function closeHelp(){
      $("helpModal").classList.remove("open");
      $("helpModal").setAttribute("aria-hidden","true");
    }

    function setFilterOptions(){
      const artists = [...new Set(state.items.map(x=>x.artist).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
      const genres  = [...new Set(state.items.map(x=>computeGenre(x)))].sort((a,b)=>a.localeCompare(b));
      const decades = [...new Set(state.items.map(x=>computeDecade(x)))].sort((a,b)=>a.localeCompare(b));

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

    function applyFilters(){
      const q = ($("q").value||"").trim().toLowerCase();
      const a = $("artist").value;
      const g = $("genre").value;
      const d = $("decade").value;

      state.filtered = state.items.filter(it=>{
        const blob = it.__blob || "";
        if(q && !blob.includes(q)) return false;
        if(a && it.artist !== a) return false;
        if(g && computeGenre(it) !== g) return false;
        if(d && computeDecade(it) !== d) return false;
        return true;
      });

      render();
    }

    // --- Image hover preview (offline_gallery style) ---
    function installHover(){
      const hoverOverlay = document.createElement("div");
      hoverOverlay.id = "imgHoverOverlay";
      hoverOverlay.innerHTML = "<img/>";
      document.body.appendChild(hoverOverlay);
      const hoverImg = hoverOverlay.querySelector("img");
      let currentImg = null;

      function positionNearThumb(img){
        const pad = 10;
        const r = img.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        // ensure overlay has size
        hoverOverlay.style.display = "block";
        const rect = hoverOverlay.getBoundingClientRect();
        const w = rect.width || 0;
        const h = rect.height || 0;

        // prefer right, else left
        let left = r.right + pad;
        if(left + w > vw - pad) left = r.left - pad - w;
        left = Math.max(pad, Math.min(left, vw - pad - w));

        // prefer align top, clamp
        let top = r.top;
        if(top + h > vh - pad) top = vh - pad - h;
        top = Math.max(pad, Math.min(top, vh - pad - h));

        hoverOverlay.style.left = left + "px";
        hoverOverlay.style.top = top + "px";
      }

      function show(img){
        const src = img.getAttribute("data-full") || img.src;
        if(!src) return;
        currentImg = img;
        hoverImg.src = src;
        hoverOverlay.style.display = "block";
        positionNearThumb(img);
      }

      function hide(){
        currentImg = null;
        hoverOverlay.style.display = "none";
      }

      document.addEventListener("mouseover", (e)=>{
        const t = e.target;
        if(t && t.classList && t.classList.contains("thumb")){
          show(t);
        }
      });
      document.addEventListener("mouseout", (e)=>{
        const t = e.target;
        if(t && t.classList && t.classList.contains("thumb")){
          hide();
        }
      });

      window.addEventListener("scroll", ()=>{
        if(currentImg) positionNearThumb(currentImg);
      }, {passive:true});
      window.addEventListener("resize", ()=>{
        if(currentImg) positionNearThumb(currentImg);
      });
    }

    // --- Click-to-sort tables by clicking header cells (offline_gallery style) ---
    function makeTableSortable(table){
      if(!table) return;
      const thead = table.querySelector("thead");
      const tbody = table.querySelector("tbody");
      if(!thead || !tbody) return;

      const ths = Array.from(thead.querySelectorAll("th"));
      const sortState = { idx: -1, dir: 1 };

      function cellText(tr, idx){
        const td = tr.children[idx];
        if(!td) return "";
        const ds = td.getAttribute("data-sort");
        return (ds || td.textContent || "").trim();
      }

      function cmp(a, b, idx){
        const ha = (ths[idx]?.textContent || "").toLowerCase();
        const av = cellText(a, idx);
        const bv = cellText(b, idx);

        if(ha.includes("price") || ha.includes("year")){
          const an = Number(av);
          const bn = Number(bv);
          const aok = Number.isFinite(an);
          const bok = Number.isFinite(bn);
          if(aok && bok) return an - bn;
          if(aok && !bok) return -1;
          if(!aok && bok) return 1;
        }
        return av.localeCompare(bv, undefined, { numeric:true, sensitivity:"base" });
      }

      function sortBy(idx){
        const rows = Array.from(tbody.querySelectorAll("tr"));
        const dir = (sortState.idx === idx) ? -sortState.dir : 1;
        sortState.idx = idx; sortState.dir = dir;
        rows.sort((ra, rb) => dir * cmp(ra, rb, idx));
        rows.forEach(r => tbody.appendChild(r));
      }

      ths.forEach((th, idx)=>{
        if(th.classList.contains("noclick")) return;
        th.title = "Click to sort";
        th.addEventListener("click", () => sortBy(idx));
      });
    }

    function render(){
      $("status").textContent = `${state.filtered.length} shown / ${state.items.length} total`;
      const tbody = $("tbody");
      tbody.innerHTML = "";

      for(const it of state.filtered){
        const rid = ridOf(it);
        const priceNum = Number(String(it.price||"").replace(/[^0-9.]/g,"")) || 0;
        const year = computeYear(it);
        const img = it.img || "";
        const fullImg = it.img_full_local || it.img_full_url || img || "";
        const url = "https://www.discogs.com/release/" + encodeURIComponent(rid);

        const inCart = state.cart[rid] ? 1 : 0;

        const tr = document.createElement("tr");
        tr.className = inCart ? "incart" : "";

        const tdPrice = document.createElement("td");
        tdPrice.className = "nowrap";
        tdPrice.setAttribute("data-sort", String(priceNum));
        tdPrice.textContent = priceNum>0 ? "$" + String(Math.round(priceNum)) : "";

        const tdCart = document.createElement("td");
        tdCart.className = "nowrap";
        const wrap = document.createElement("div");
        wrap.className = "iconstack";

        const bPlus = document.createElement("button");
        bPlus.className = "iconbtn";
        bPlus.type = "button";
        bPlus.textContent = "+";
        bPlus.disabled = inCart > 0;
        bPlus.addEventListener("click", ()=>{
          if(state.cart[rid]) return;
          state.cart[rid] = 1;
          saveCart(); updateCartButton(); render();
        });

        const bMinus = document.createElement("button");
        bMinus.className = "iconbtn";
        bMinus.type = "button";
        bMinus.textContent = "−";
        bMinus.disabled = inCart <= 0;
        bMinus.addEventListener("click", ()=>{
          if(!state.cart[rid]) return;
          delete state.cart[rid];
          saveCart(); updateCartButton(); render();
        });

        wrap.appendChild(bPlus);
        wrap.appendChild(bMinus);
        tdCart.appendChild(wrap);

        const tdCover = document.createElement("td");
        const im = document.createElement("img");
        im.className = "thumb";
        im.loading = "lazy";
        im.src = img;
        im.alt = (it.artist||"") + " — " + (it.title||"");
        im.setAttribute("data-full", fullImg || img);
        tdCover.appendChild(im);

        const tdArtist = document.createElement("td");
        tdArtist.textContent = it.artist || "";
        tdArtist.setAttribute("data-sort", it.artist || "");

        const tdTitle = document.createElement("td");
        tdTitle.setAttribute("data-sort", it.title || "");
        const a = document.createElement("a");
        a.className = "dlink";
        a.href = url;
        a.target = "_blank";
        a.rel = "noreferrer";
        a.textContent = it.title || "";
        tdTitle.appendChild(a);

        const tdYear = document.createElement("td");
        tdYear.className = "nowrap";
        const yearNum = Number(year || "");
        tdYear.setAttribute("data-sort", Number.isFinite(yearNum) ? String(yearNum) : "");
        tdYear.textContent = year;

        const tdFmt = document.createElement("td");
        tdFmt.className = "nowrap";
        tdFmt.textContent = it.format || "";

        tr.appendChild(tdPrice);
        tr.appendChild(tdCart);
        tr.appendChild(tdCover);
        tr.appendChild(tdArtist);
        tr.appendChild(tdTitle);
        tr.appendChild(tdYear);
        tr.appendChild(tdFmt);

        tbody.appendChild(tr);
      }

      $("tbl").style.display = "table";
      setFilterOptions();
    }

    function boot(){
      // set header height for sticky TH offset
      const header = $("header");
      if(header){
        const h = header.getBoundingClientRect().height;
        document.documentElement.style.setProperty("--header-h", Math.round(h) + "px");
        document.body.style.paddingTop = (Math.round(h) + 12) + "px";
        window.addEventListener("resize", ()=>{
          const hh = header.getBoundingClientRect().height;
          document.documentElement.style.setProperty("--header-h", Math.round(hh) + "px");
        });
      }

      loadCart();
      updateCartButton();

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

      $("helpOpen").addEventListener("click", openHelp);
      $("helpClose").addEventListener("click", closeHelp);
      $("helpModal").addEventListener("click", (e)=>{ if(e.target===$("helpModal")) closeHelp(); });

      document.addEventListener("keydown", (e)=>{ if(e.key==="Escape"){ closeCart(); closeHelp(); } });

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
        saveCart(); updateCartButton(); render();
        openCart();
      });

      // Keep the control bar visible and prevent content from sliding underneath it
      function syncHeaderPad(){
        const h = document.getElementById("header");
        if(!h) return;
        document.body.style.paddingTop = (h.offsetHeight || 0) + "px";
      }
      syncHeaderPad();
      window.addEventListener("resize", syncHeaderPad, {passive:true});

      fetch("store_inventory.json", {cache:"no-store"})
        .then(r=>{
          if(!r.ok) throw new Error("HTTP "+r.status);
          return r.json();
        })
        .then(j=>{
          state.items = (j && j.items) ? j.items : [];
          // precompute search blobs (avoid recompute on each filter)
          for(const it of state.items){ it.__blob = searchBlob(it); }
          state.filtered = state.items.slice();

          $("status").textContent = `${state.items.length} total`;
          render();
          applyFilters(); // ensures status text uses filtered count + options in sync
          makeTableSortable($("tbl"));
          installHover();
        })
        .catch(err=>{
          $("status").textContent = "Failed to load store_inventory.json: " + err;
          console.error(err);
        });
    }

    boot();
  })();
  </script>
</body>
</html>
"""
def main() -> int:
    # Allow running store_webpage.py directly without .bat
    load_env_file(Path(r"D:\records\.env"))

    records_home = Path(env("RECORDS_HOME", r"D:\records"))
    records_out = Path(env("RECORDS_OUT", str(records_home / "outputs")))
    title = env("STORE_TITLE", "Record Store") or "Record Store"

    OUT_ROOT = records_out / "store"
    SITE_DIR = OUT_ROOT / "site"
    ensure_dir(SITE_DIR)

    inv_path = SITE_DIR / "store_inventory.json"
    if not inv_path.exists():
        print(f"ERROR: Missing inventory json: {inv_path}", flush=True)
        print("Run store_data.py first to fetch/build inventory.", flush=True)
        return 2

    # Enrich inventory json WITHOUT Discogs API:
    # - If offline_gallery/records.csv exists, fill missing years
    # - If site/images/ contains full-size images (named by md5_16(url)+ext), attach img_full_local
    #   and prefer local images for thumbnails + hover previews.
    try:
        import json as _json
        import hashlib as _hashlib
        import csv as _csv
        from urllib.parse import urlparse as _urlparse

        def _md5_16(s: str) -> str:
            return _hashlib.md5(s.encode("utf-8", errors="ignore")).hexdigest()[:16]

        def _guess_full_discogs_url(u: str) -> str:
            # Discogs often provides thumbnail URLs with an /rs:fit/.../ segment.
            # If we see the base64 image-path marker "/czM6", we can drop the resize segment.
            if not isinstance(u, str) or not u:
                return ""
            if "/rs:" in u and "/czM6" in u:
                try:
                    pre = u.split("/rs:", 1)[0]
                    tail = u[u.find("/czM6") :]
                    return pre + tail
                except Exception:
                    return u
            return u

        # Load optional year map from offline_gallery
        year_map: dict[int, str] = {}
        try:
            og_csv = records_out / "offline_gallery" / "records.csv"
            if og_csv.exists():
                with og_csv.open("r", encoding="utf-8", errors="replace", newline="") as f:
                    r = _csv.DictReader(f)
                    for row in r:
                        rid_s = (row.get("release_id") or row.get("rid") or row.get("id") or "").strip()
                        if not rid_s:
                            continue
                        try:
                            rid_i = int(rid_s)
                        except Exception:
                            continue
                        y = (row.get("year") or row.get("released") or "").strip()
                        if y:
                            year_map[rid_i] = y
        except Exception:
            year_map = {}

        images_dir = SITE_DIR / "images"
        inv = _json.loads(inv_path.read_text(encoding="utf-8", errors="replace"))
        items = inv.get("items") if isinstance(inv, dict) else None

        if isinstance(items, list):
            changed = False
            for it in items:
                if not isinstance(it, dict):
                    continue

                # Fill missing year from offline_gallery
                try:
                    rid_i = int(str(it.get("rid") or it.get("release_id") or "").strip())
                except Exception:
                    rid_i = None
                if rid_i is not None and (not str(it.get("year") or "").strip()):
                    y = year_map.get(rid_i, "")
                    if y:
                        it["year"] = y
                        changed = True

                # Prefer full-size local images if present
                if images_dir.exists():
                    base_url = (it.get("img_full_url") or it.get("img") or "").strip()
                    if base_url:
                        full_url = _guess_full_discogs_url(base_url)
                        # Determine extension from URL path, default to .jpeg
                        try:
                            path = _urlparse(full_url).path or ""
                            ext = Path(path).suffix.lower()
                        except Exception:
                            ext = ""
                        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                            ext = ".jpeg"
                        name = _md5_16(full_url) + ext
                        local_path = images_dir / name
                        if local_path.exists() and local_path.stat().st_size > 0:
                            rel = f"images/{name}"
                            if it.get("img_full_local") != rel:
                                it["img_full_local"] = rel
                                changed = True
                            if it.get("img_full_url") != full_url:
                                it["img_full_url"] = full_url
                                changed = True
                            # Use the local full-size image as the thumbnail too (browser will scale down).
                            if it.get("img") != rel:
                                it["img"] = rel
                                changed = True

            if changed:
                inv_path.write_text(_json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


    html_path = SITE_DIR / "index.html"
    html_out = HTML.replace("<title>Record Store</title>", f"<title>{title}</title>")
    html_path.write_text(html_out, encoding="utf-8")
    print(f"Site: {html_path}", flush=True)
    print("Done.", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
