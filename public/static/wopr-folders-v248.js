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
    b.className = BTN_CLASS + " mini-btn";
    b.textContent = "📁 Dossier";
    b.title = title;
    b.setAttribute("aria-label", title);
    b.dataset.folderUrl = url;
    Object.assign(b.style, {
      display:"inline-flex",
      alignItems:"center",
      justifyContent:"center",
      width:"auto",
      minWidth:"0",
      height:"auto",
      padding:"4px 7px",
      margin:"2px 0 0 4px",
      cursor:"pointer",
      whiteSpace:"nowrap",
      boxSizing:"border-box"
    });
    b.addEventListener("click", ev => {
      ev.preventDefault();
      ev.stopPropagation();
      openFolder(url);
    });
    return b;
  }

  function bindStaticFolderButtons() {
    document.querySelectorAll("[data-wopr-folder-url]").forEach(btn => {
      if (btn.dataset.woprFolderBound === "1") return;
      btn.dataset.woprFolderBound = "1";
      btn.addEventListener("click", ev => {
        ev.preventDefault();
        ev.stopPropagation();
        openFolder(btn.dataset.woprFolderUrl);
      });
    });
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
    // Géré directement dans le template depuis 2.3.252.
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
    // Géré directement dans le template depuis 2.3.252.
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

  function markPage() {
    document.body.classList.toggle("wopr-page-factures", location.pathname === "/factures");
    document.body.classList.toggle("wopr-page-devis", location.pathname === "/devis");
    document.body.classList.toggle("wopr-page-suivi", location.pathname === "/suivi");
    document.body.classList.toggle("wopr-page-achats-ventes", /^\/achats-ventes(?:\/|$)/.test(location.pathname));
  }

  function wrapActionCell(cell, columns) {
    if (!cell || cell.dataset.woprActionsWrapped === "1") return;

    const interactive = Array.from(cell.children).filter(el => {
      if (el.classList?.contains("wopr-action-grid")) return false;
      const tag = el.tagName;
      return ["A","BUTTON","SELECT","FORM","SPAN"].includes(tag);
    });
    if (!interactive.length) return;

    const grid = document.createElement("div");
    grid.className = "wopr-action-grid";
    grid.dataset.columns = String(columns || 3);

    interactive.forEach(el => grid.appendChild(el));
    cell.appendChild(grid);
    cell.dataset.woprActionsWrapped = "1";
  }

  function uniformizeActions() {
    if (location.pathname === "/factures" || location.pathname === "/devis") {
      document.querySelectorAll("td.invoice-list-actions, td.quote-list-actions").forEach(cell => {
        wrapActionCell(cell, 3);
      });
    }

    if (location.pathname === "/suivi") {
      document.querySelectorAll("table tbody tr").forEach(row => {
        const cells = row.querySelectorAll("td");
        if (!cells.length) return;
        const cell = cells[cells.length - 1];
        if (cell.hasAttribute("colspan")) return;

        const controls = cell.querySelectorAll("a,button,form,select,input[type=button],input[type=submit]");
        if (controls.length >= 3) wrapActionCell(cell, 2);
      });

      document.querySelectorAll("table").forEach(table => {
        if (table.querySelector("th") && table.querySelectorAll("tbody tr").length) {
          table.classList.add("wopr-light-table");
        }
      });
    }

    if (/^\/achats-ventes(?:\/|$)/.test(location.pathname)) {
      document.querySelectorAll(".ledger-table, .ledger-month table, table").forEach(table => {
        if (table.querySelector("th") && table.querySelectorAll("tbody tr").length) {
          table.classList.add("wopr-light-table");
        }
      });

      document.querySelectorAll("td.ledger-row-actions, .ledger-row-actions").forEach(cell => {
        wrapActionCell(cell, 2);
      });
    }

  }

  function scanAll() {
    markPage();
    bindStaticFolderButtons();
    scanFactures();
    scanSuivi();
    scanDevis();
    scanLedger();
    scanRepairDetail();
    uniformizeActions();
  }

  document.addEventListener("DOMContentLoaded", scanAll);
  window.addEventListener("load", scanAll);
  new MutationObserver(scanAll).observe(document.documentElement, {subtree:true, childList:true});
})();
