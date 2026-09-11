(() => {
  "use strict";

  const BTN_CLASS = "wopr-folder-v248";

  function toast(text, ok=true) {
    let t = document.getElementById("wopr-folder-v248-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "wopr-folder-v248-toast";
      Object.assign(t.style, {
        position:"fixed", right:"18px", bottom:"18px", zIndex:"100000",
        padding:"8px 11px", borderRadius:"7px", color:"#fff",
        font:"12px sans-serif", boxShadow:"0 2px 10px rgba(0,0,0,.25)",
        opacity:"0", transition:"opacity .15s"
      });
      document.body.appendChild(t);
    }
    t.textContent = text;
    t.style.background = ok ? "#207a41" : "#a12e2e";
    t.style.opacity = "1";
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.style.opacity = "0", 1800);
  }

  async function openFolder(url) {
    try {
      const r = await fetch(url, {method:"GET", cache:"no-store", headers:{"X-Requested-With":"XMLHttpRequest"}});
      if (!r.ok) throw new Error((await r.text()) || `HTTP ${r.status}`);
      toast("📁 Dossier ouvert");
    } catch (e) {
      toast(`Dossier : ${e.message}`, false);
    }
  }

  function makeButton(url, title) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = BTN_CLASS;
    b.textContent = "📁 Dossier";
    b.title = title;
    b.setAttribute("aria-label", title);
    b.dataset.folderUrl = url;
    Object.assign(b.style, {
      display:"block",
      width:"100%",
      minWidth:"0",
      height:"auto",
      padding:"4px 7px",
      margin:"4px 0 0 0",
      border:"1px solid #c7d2df",
      borderRadius:"6px",
      background:"#fff",
      cursor:"pointer",
      fontSize:"11px",
      lineHeight:"1.15",
      verticalAlign:"middle",
      boxSizing:"border-box",
      whiteSpace:"nowrap"
    });
    b.addEventListener("click", ev => {
      ev.preventDefault();
      ev.stopPropagation();
      openFolder(url);
    });
    return b;
  }

  function rowRepairId(row) {
    const html = row?.outerHTML || "";
    let m = html.match(/\/repair\/(\d+)(?:\/|["'?#])/i);
    if (m) return m[1];
    // Certains écrans stockent juste l'id en data-*.
    for (const el of row?.querySelectorAll?.("[data-repair-id],[data-rid]") || []) {
      const v = el.dataset.repairId || el.dataset.rid;
      if (/^\d+$/.test(v || "")) return v;
    }
    return null;
  }

  function rowQuoteId(row) {
    const html = row?.outerHTML || "";
    const m = html.match(/\/devis\/(\d+)(?:\/|["'?#])/i);
    return m ? m[1] : null;
  }

  function actionCell(row) {
    return row.querySelector(".ledger-row-actions,.actions,.action,.row-actions,td:last-child") || row;
  }

  function addAtEnd(row, url, title, key) {
    if (!row || !url) return;
    if (row.querySelector(`.${BTN_CLASS}[data-folder-key="${key}"]`)) return;
    const b = makeButton(url, title);
    b.dataset.folderKey = key;
    actionCell(row).appendChild(b);
  }

  function scanFactures() {
    if (location.pathname !== "/factures") return;
    document.querySelectorAll("tbody tr, table tr").forEach(row => {
      const rid = rowRepairId(row);
      if (!rid) return;
      addAtEnd(row, `/repair/${rid}/invoice-folder`, "Ouvrir le dossier de cette facture", `invoice-${rid}`);
    });
  }

  function scanSuivi() {
    if (location.pathname !== "/suivi") return;
    document.querySelectorAll("tbody tr, table tr").forEach(row => {
      const rid = rowRepairId(row);
      if (!rid) return;
      addAtEnd(row, `/repair/${rid}/intake-folder`, "Ouvrir le dossier du suivi", `intake-${rid}`);
    });
  }

  function scanDevis() {
    if (location.pathname !== "/devis") return;
    document.querySelectorAll("tbody tr, table tr").forEach(row => {
      const qid = rowQuoteId(row);
      if (!qid) return;
      addAtEnd(row, `/devis/${qid}/folder`, "Ouvrir le dossier de ce devis", `quote-${qid}`);
    });
  }

  function scanLedger() {
    // Géré directement dans achats_ventes.html depuis 2.3.251.
    // Cela garantit : bouton Ouvrir => bouton Dossier, sans exception ni doublon.
  }

  function scanRepairDetail() {
    const m = location.pathname.match(/^\/repair\/(\d+)\/?$/);
    if (!m) return;
    const rid = m[1];
    document.querySelectorAll("a,button,input[type=button],input[type=submit]").forEach(el => {
      const text = String(el.innerText || el.textContent || el.value || "").toLowerCase();
      if (!text.includes("pdf")) return;
      const parent = el.parentElement || el;
      if ((text.includes("suivi") || text.includes("prise en charge")) &&
          !parent.querySelector(`.${BTN_CLASS}[data-folder-key="detail-intake-${rid}"]`)) {
        const b = makeButton(`/repair/${rid}/intake-folder`, "Ouvrir le dossier du suivi");
        b.dataset.folderKey = `detail-intake-${rid}`;
        el.insertAdjacentElement("afterend", b);
      }
      if (text.includes("facture") &&
          !parent.querySelector(`.${BTN_CLASS}[data-folder-key="detail-invoice-${rid}"]`)) {
        const b = makeButton(`/repair/${rid}/invoice-folder`, "Ouvrir le dossier de la facture");
        b.dataset.folderKey = `detail-invoice-${rid}`;
        el.insertAdjacentElement("afterend", b);
      }
    });
  }

  function scanAll() {
    scanFactures();
    scanSuivi();
    scanDevis();
    scanLedger();
    scanRepairDetail();
  }

  document.addEventListener("DOMContentLoaded", scanAll);
  window.addEventListener("load", scanAll);
  new MutationObserver(scanAll).observe(document.documentElement, {subtree:true, childList:true});
})();