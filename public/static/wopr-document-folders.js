(() => {
  "use strict";

  const patterns = [
    { re: /^\/repair\/(\d+)\/intake\.pdf$/, endpoint: id => `/repair/${id}/intake-folder` },
    { re: /^\/repair\/(\d+)\/invoice\.pdf$/, endpoint: id => `/repair/${id}/invoice-folder` },
    { re: /^\/devis\/(\d+)\/pdf$/, endpoint: id => `/devis/${id}/folder` },
    { re: /^\/achats-ventes\/vente\/(\d+)\/facture$/, endpoint: id => `/achats-ventes/vente/${id}/folder` }
  ];

  function routeFor(anchor) {
    let url;
    try {
      url = new URL(anchor.href, window.location.origin);
    } catch (_) {
      return null;
    }
    for (const item of patterns) {
      const match = url.pathname.match(item.re);
      if (match) return item.endpoint(match[1]);
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

  function addButton(anchor, endpoint) {
    if (anchor.dataset.woprFolderButton === "1") return;
    anchor.dataset.woprFolderButton = "1";

    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "📁";
    button.title = "Ouvrir le dossier du PDF archivé";
    button.setAttribute("aria-label", "Ouvrir le dossier du PDF archivé");
    button.className = anchor.className || "";
    button.dataset.woprFolderHelper = "1";

    Object.assign(button.style, {
      marginLeft: "4px",
      minWidth: "28px",
      width: "28px",
      padding: "2px 4px",
      lineHeight: "1.2",
      verticalAlign: "middle",
      whiteSpace: "nowrap"
    });

    button.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      openFolder(endpoint);
    });

    anchor.insertAdjacentElement("afterend", button);
  }

  function scan() {
    document.querySelectorAll("a[href]").forEach(anchor => {
      const endpoint = routeFor(anchor);
      if (endpoint) addButton(anchor, endpoint);
    });
  }

  document.addEventListener("DOMContentLoaded", scan);

  const observer = new MutationObserver(scan);
  observer.observe(document.documentElement, {childList: true, subtree: true});
})();
