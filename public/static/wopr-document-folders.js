(() => {
  "use strict";

  const routePatterns = [
    { re: /\/repair\/(\d+)\/intake\.pdf(?:[?#].*)?$/i, endpoint: id => `/repair/${id}/intake-folder`, kind: "intake" },
    { re: /\/repair\/(\d+)\/invoice\.pdf(?:[?#].*)?$/i, endpoint: id => `/repair/${id}/invoice-folder`, kind: "invoice" },
    { re: /\/devis\/(\d+)\/pdf(?:[?#].*)?$/i, endpoint: id => `/devis/${id}/folder`, kind: "quote" },
    { re: /\/achats-ventes\/vente\/(\d+)\/facture(?:[?#].*)?$/i, endpoint: id => `/achats-ventes/vente/${id}/folder`, kind: "invoice" }
  ];

  function routeInfo(value) {
    const text = String(value || "");
    for (const item of routePatterns) {
      const match = text.match(item.re);
      if (match) return {endpoint: item.endpoint(match[1]), kind: item.kind};
    }
    return null;
  }

  function infoForElement(el) {
    if (!el) return null;
    const values = [
      el.getAttribute?.("href"),
      el.getAttribute?.("formaction"),
      el.getAttribute?.("action"),
      el.getAttribute?.("data-href"),
      el.getAttribute?.("data-url"),
      el.getAttribute?.("data-pdf-url"),
      el.getAttribute?.("onclick"),
      el.form?.getAttribute?.("action")
    ];
    for (const value of values) {
      const info = routeInfo(value);
      if (info) return info;
    }
    return null;
  }

  function notify(message, ok = true) {
    let box = document.getElementById("wopr-folder-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "wopr-folder-toast";
      Object.assign(box.style, {
        position: "fixed", right: "18px", bottom: "18px", zIndex: "99999",
        padding: "9px 12px", borderRadius: "8px", fontSize: "13px",
        boxShadow: "0 2px 12px rgba(0,0,0,.25)", opacity: "0",
        transition: "opacity .2s ease", pointerEvents: "none"
      });
      document.body.appendChild(box);
    }
    box.textContent = message;
    box.style.background = ok ? "#1f7a3f" : "#9b2c2c";
    box.style.color = "#fff";
    box.style.opacity = "1";
    clearTimeout(box._timer);
    box._timer = setTimeout(() => box.style.opacity = "0", 2200);
  }

  async function openFolder(endpoint) {
    try {
      const response = await fetch(endpoint, {
        method: "GET",
        cache: "no-store",
        headers: {"X-Requested-With": "XMLHttpRequest"}
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Erreur HTTP ${response.status}`);
      }
      notify("📁 Dossier ouvert");
    } catch (error) {
      notify(`Erreur : ${error.message}`, false);
    }
  }

  function addFolderButton(target, endpoint) {
    if (!target || !endpoint || target.dataset.woprFolderButton === "1") return;
    target.dataset.woprFolderButton = "1";

    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "📁";
    button.title = "Ouvrir le dossier du PDF archivé";
    button.setAttribute("aria-label", "Ouvrir le dossier du PDF archivé");
    button.dataset.woprFolderHelper = "1";

    Object.assign(button.style, {
      marginLeft: "3px",
      width: "18px",
      minWidth: "18px",
      height: "18px",
      minHeight: "18px",
      padding: "0",
      border: "1px solid #c9c9c9",
      borderRadius: "4px",
      background: "#fff",
      cursor: "pointer",
      fontSize: "10px",
      lineHeight: "16px",
      verticalAlign: "middle",
      boxSizing: "border-box"
    });

    button.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      openFolder(endpoint);
    });

    // Dans les tableaux : le bouton reste DANS la cellule, sans élargir la colonne.
    const cell = target.closest("td, th");
    if (cell) {
      if (window.getComputedStyle(cell).position === "static") cell.style.position = "relative";
      Object.assign(button.style, {
        position: "absolute",
        right: "1px",
        bottom: "1px",
        marginLeft: "0",
        zIndex: "2"
      });
      cell.appendChild(button);
    } else {
      target.insertAdjacentElement("afterend", button);
    }
  }

  function contextKind(el) {
    const direct = infoForElement(el);
    if (direct) return direct;

    const path = window.location.pathname;
    const repairMatch = path.match(/^\/repair\/(\d+)\/?$/);
    if (!repairMatch) return null;
    const rid = repairMatch[1];

    // Cherche le texte de la zone autour du bouton pour distinguer suivi/facture.
    let node = el;
    let text = "";
    for (let i = 0; i < 4 && node; i++, node = node.parentElement) {
      text += " " + String(node.innerText || node.textContent || "").toLowerCase();
    }
    const own = String(el.innerText || el.textContent || el.value || "").toLowerCase();

    if (text.includes("facture") || own.includes("facture")) {
      return {endpoint: `/repair/${rid}/invoice-folder`, kind: "invoice"};
    }
    if (
      text.includes("suivi") ||
      text.includes("prise en charge") ||
      own.includes("pdf") ||
      own.includes("générer")
    ) {
      return {endpoint: `/repair/${rid}/intake-folder`, kind: "intake"};
    }
    return null;
  }

  function removeDuplicateSimpleInvoiceButton() {
    const candidates = Array.from(document.querySelectorAll("a[href], button, input[type='button'], input[type='submit']"))
      .filter(el => {
        const values = [
          el.getAttribute?.("href"),
          el.getAttribute?.("formaction"),
          el.getAttribute?.("onclick"),
          el.form?.getAttribute?.("action")
        ].join(" ");
        const text = String(el.innerText || el.textContent || el.value || "").trim().toLowerCase();
        return values.includes("/invoice/simple") && text.includes("facture simple");
      });

    // Le menu est dans le haut du DOM : on garde le premier et on masque le doublon principal.
    if (candidates.length > 1) {
      candidates.slice(1).forEach(el => {
        const wrapper = el.closest("form");
        (wrapper || el).style.display = "none";
      });
    }
  }

  function scan() {
    removeDuplicateSimpleInvoiceButton();

    // Liens/boutons qui pointent directement vers un PDF.
    document.querySelectorAll("a[href], button, input[type='button'], input[type='submit'], form[action]").forEach(el => {
      if (el.dataset?.woprFolderHelper === "1") return;
      const info = infoForElement(el);
      if (info) {
        const target = el.tagName === "FORM"
          ? el.querySelector("button, input[type='submit'], a") || el
          : el;
        addFolderButton(target, info.endpoint);
      }
    });

    // Page d'un suivi : même si le bouton PDF est généré par JS ou n'a pas d'URL directe.
    if (/^\/repair\/\d+\/?$/.test(window.location.pathname)) {
      document.querySelectorAll("button, a, input[type='button'], input[type='submit']").forEach(el => {
        if (el.dataset?.woprFolderHelper === "1" || el.dataset?.woprFolderButton === "1") return;
        const text = String(el.innerText || el.textContent || el.value || "").toLowerCase();
        if (!text.includes("pdf") && !text.includes("générer")) return;
        const info = contextKind(el);
        if (info) addFolderButton(el, info.endpoint);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", scan);
  const observer = new MutationObserver(scan);
  observer.observe(document.documentElement, {childList: true, subtree: true});
})();
