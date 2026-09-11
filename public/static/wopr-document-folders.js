(() => {
  "use strict";

  const routePatterns = [
    {
      re: /\/repair\/(\d+)\/intake\.pdf(?:[?#].*)?$/i,
      endpoint: id => `/repair/${id}/intake-folder`
    },
    {
      re: /\/repair\/(\d+)\/invoice\.pdf(?:[?#].*)?$/i,
      endpoint: id => `/repair/${id}/invoice-folder`
    },
    {
      re: /\/devis\/(\d+)\/pdf(?:[?#].*)?$/i,
      endpoint: id => `/devis/${id}/folder`
    },
    {
      re: /\/achats-ventes\/vente\/(\d+)\/facture(?:[?#].*)?$/i,
      endpoint: id => `/achats-ventes/vente/${id}/folder`
    }
  ];

  function endpointFromText(value) {
    const text = String(value || "");
    for (const item of routePatterns) {
      const match = text.match(item.re);
      if (match) return item.endpoint(match[1]);
    }
    return null;
  }

  function endpointForElement(el) {
    if (!el) return null;

    const values = [
      el.getAttribute?.("href"),
      el.getAttribute?.("formaction"),
      el.getAttribute?.("action"),
      el.getAttribute?.("data-href"),
      el.getAttribute?.("data-url"),
      el.getAttribute?.("data-pdf-url"),
      el.getAttribute?.("onclick")
    ];

    for (const value of values) {
      const endpoint = endpointFromText(value);
      if (endpoint) return endpoint;
    }

    // Cas fréquent : bouton submit dans un formulaire dont action pointe vers le PDF.
    if (el.form) {
      const endpoint = endpointFromText(el.form.getAttribute("action"));
      if (endpoint) return endpoint;
    }

    // Dernier filet pour les boutons JavaScript contenant l'URL dans leur HTML parent.
    if (el.parentElement) {
      const endpoint = endpointFromText(el.parentElement.innerHTML);
      if (endpoint) return endpoint;
    }

    return null;
  }

  function notify(message, ok = true) {
    let box = document.getElementById("wopr-folder-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "wopr-folder-toast";
      Object.assign(box.style, {
        position: "fixed",
        right: "18px",
        bottom: "18px",
        zIndex: "99999",
        padding: "9px 12px",
        borderRadius: "8px",
        fontSize: "13px",
        boxShadow: "0 2px 12px rgba(0,0,0,.25)",
        opacity: "0",
        transition: "opacity .2s ease",
        pointerEvents: "none"
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

    // Ne pas recopier la classe du bouton "Ouvrir" : certaines feuilles CSS
    // imposent une largeur minimale et faisaient déborder le bouton dossier.
    Object.assign(button.style, {
      marginLeft: "3px",
      width: "19px",
      minWidth: "19px",
      height: "22px",
      minHeight: "22px",
      padding: "0",
      border: "1px solid #c9c9c9",
      borderRadius: "4px",
      background: "#fff",
      cursor: "pointer",
      fontSize: "11px",
      lineHeight: "18px",
      verticalAlign: "middle",
      boxSizing: "border-box"
    });

    button.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      openFolder(endpoint);
    });

    // Si on est dans une cellule de tableau, on évite toute influence sur la largeur
    // de la colonne : petit bouton absolu à droite de la cellule.
    const cell = target.closest("td, th");
    if (cell) {
      const computed = window.getComputedStyle(cell);
      if (computed.position === "static") cell.style.position = "relative";

      Object.assign(button.style, {
        position: "absolute",
        right: "2px",
        top: "50%",
        transform: "translateY(-50%)",
        marginLeft: "0",
        zIndex: "2"
      });

      // Un peu d'air pour ne pas superposer le bouton "Ouvrir".
      const currentPadding = parseFloat(window.getComputedStyle(cell).paddingRight || "0") || 0;
      if (currentPadding < 23) cell.style.paddingRight = "23px";
      cell.appendChild(button);
    } else {
      target.insertAdjacentElement("afterend", button);
    }
  }

  function scan() {
    // Liens directs PDF.
    document.querySelectorAll("a[href]").forEach(el => {
      const endpoint = endpointForElement(el);
      if (endpoint) addFolderButton(el, endpoint);
    });

    // Boutons "Générer PDF", "PDF", etc. (formaction / onclick / data-url).
    document.querySelectorAll("button, input[type='button'], input[type='submit']").forEach(el => {
      if (el.dataset.woprFolderHelper === "1") return;
      const endpoint = endpointForElement(el);
      if (endpoint) addFolderButton(el, endpoint);
    });

    // Formulaires dont l'action elle-même génère un PDF.
    document.querySelectorAll("form[action]").forEach(form => {
      const endpoint = endpointForElement(form);
      if (!endpoint) return;
      const target = form.querySelector("button[type='submit'], input[type='submit'], button");
      if (target) addFolderButton(target, endpoint);
    });
  }

  document.addEventListener("DOMContentLoaded", scan);

  const observer = new MutationObserver(scan);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });
})();
