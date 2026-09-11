(() => {
  "use strict";

  // WOPR 2.3.284
  // Dernier filet de sécurité du thème 8-BIT :
  // les styles d'action sont appliqués en INLINE + !important,
  // donc aucune feuille CSS ne peut les écraser ensuite.

  const MANAGED = [
    "--wopr8-kind",
    "appearance", "-webkit-appearance",
    "border", "border-radius",
    "background", "background-color", "background-image",
    "color", "box-shadow",
    "font-family", "font-size", "font-weight", "line-height",
    "letter-spacing", "text-transform", "text-shadow",
    "min-height", "padding", "transform", "transition", "clip-path"
  ];

  const palette = {
    open:    {bg:"#dcecff", fg:"#103d66"},
    send:    {bg:"#ddf5e6", fg:"#14502e"},
    edit:    {bg:"#ffedbd", fg:"#6b4500"},
    folder:  {bg:"#eadcff", fg:"#4c2477"},
    del:     {bg:"#ffdada", fg:"#7c2020"},
    neutral: {bg:"#f4f7f9", fg:"#263746"}
  };

  function kindOf(el){
    if (!el || !el.classList) return null;

    if (el.classList.contains("wopr-action-delete")) return "del";
    if (el.classList.contains("danger-btn") &&
        (el.closest(".ledger-normal-actions") || el.closest(".quote-list-actions"))) return "del";

    if (el.classList.contains("wopr-action-edit") ||
        el.classList.contains("ledger-edit-btn")) return "edit";

    if (el.classList.contains("wopr-action-folder") ||
        el.classList.contains("wopr-action-special") ||
        el.classList.contains("wopr-folder-v248") ||
        el.classList.contains("ledger-folder-btn")) return "folder";

    if (el.classList.contains("wopr-action-send") ||
        el.classList.contains("wopr-action-save")) return "send";

    if (el.classList.contains("wopr-action-neutral")) return "neutral";

    if (el.classList.contains("wopr-action-open") ||
        el.classList.contains("wopr-print-pdf-btn")) return "open";

    return null;
  }

  function setImp(el, name, value){
    el.style.setProperty(name, value, "important");
  }

  function stylePixel(el, kind){
    const p = palette[kind] || palette.neutral;

    el.dataset.wopr8Runtime = "1";
    el.dataset.wopr8Kind = kind;

    // Pour les SELECT "Facture PDF", conserver le contrôle natif de la flèche.
    const isSelect = el.tagName === "SELECT";
    setImp(el, "appearance", isSelect ? "auto" : "none");
    setImp(el, "-webkit-appearance", isSelect ? "menulist" : "none");

    setImp(el, "border", "2px solid #07131d");
    setImp(el, "border-radius", "0");
    setImp(el, "background", p.bg);
    setImp(el, "background-color", p.bg);
    setImp(el, "background-image", "none");
    setImp(el, "color", p.fg);
    setImp(el, "box-shadow",
      "inset 2px 2px 0 rgba(255,255,255,.70), inset -1px -1px 0 rgba(0,0,0,.12), 2px 2px 0 #07131d");
    setImp(el, "font-family", '"DejaVu Sans Mono","Liberation Mono",Consolas,monospace');
    setImp(el, "font-size", "10px");
    setImp(el, "font-weight", "800");
    setImp(el, "line-height", "1.05");
    setImp(el, "letter-spacing", "0");
    setImp(el, "text-transform", "uppercase");
    setImp(el, "text-shadow", "none");
    setImp(el, "min-height", "24px");
    setImp(el, "padding", "4px 7px");
    setImp(el, "transform", "none");
    setImp(el, "transition", "none");
    setImp(el, "clip-path", "none");
  }

  function clearPixel(el){
    if (!el || el.dataset.wopr8Runtime !== "1") return;
    for (const name of MANAGED) {
      if (name.startsWith("--")) continue;
      el.style.removeProperty(name);
    }
    delete el.dataset.wopr8Runtime;
    delete el.dataset.wopr8Kind;
  }

  function candidates(root=document){
    return root.querySelectorAll([
      ".wopr-action-open",
      ".wopr-action-send",
      ".wopr-action-save",
      ".wopr-action-edit",
      ".wopr-action-folder",
      ".wopr-action-special",
      ".wopr-action-delete",
      ".wopr-action-neutral",
      ".wopr-folder-v248",
      ".wopr-print-pdf-btn",
      ".ledger-edit-btn",
      ".ledger-folder-btn",
      ".ledger-normal-actions .danger-btn"
    ].join(","));
  }

  function applyAll(root=document){
    const on = document.body.classList.contains("theme-8bit");
    candidates(root).forEach(el => {
      if (!on) {
        clearPixel(el);
        return;
      }
      const kind = kindOf(el);
      if (kind) stylePixel(el, kind);
    });
  }

  // Applique après le rendu initial et après les autres scripts defer.
  function boot(){
    applyAll(document);

    // Les boutons Facture / Dossier peuvent être créés dynamiquement.
    const mo = new MutationObserver(records => {
      let needsFull = false;
      for (const rec of records) {
        if (rec.type === "attributes" && rec.target === document.body) {
          needsFull = true;
          continue;
        }
        rec.addedNodes.forEach(node => {
          if (!(node instanceof Element)) return;
          const kind = kindOf(node);
          if (kind && document.body.classList.contains("theme-8bit")) stylePixel(node, kind);
          applyAll(node);
        });
      }
      if (needsFull) applyAll(document);
    });

    mo.observe(document.body, {
      subtree:true,
      childList:true,
      attributes:true,
      attributeFilter:["class"]
    });

    // Le select de thème modifie la classe du body.
    const themeSelect = document.getElementById("themeSelect");
    if (themeSelect) {
      themeSelect.addEventListener("change", () => {
        requestAnimationFrame(() => applyAll(document));
      });
    }

    // Une seconde passe couvre les MutationObservers des autres scripts.
    requestAnimationFrame(() => requestAnimationFrame(() => applyAll(document)));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, {once:true});
  } else {
    boot();
  }
})();
