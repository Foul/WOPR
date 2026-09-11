(() => {
  "use strict";

  /*
   * WOPR 2.3.226
   * Le navigateur ne permet pas de déclencher de façon fiable l'impression
   * d'un PDF téléchargé dans un iframe. On ouvre donc directement le PDF
   * en mode "inline" dans son lecteur PDF natif : plus de téléchargement
   * automatique, plus de page blanche.
   */

  function frenchPdfUrl(select) {
    const options = Array.from(select.options || []).filter(o => o.value);
    if (!options.length) return "";

    const french = options.find(o => /(?:[?&])lang=fr(?:&|$)/i.test(o.value));
    return (french || options[0]).value;
  }

  function pdfKind(select) {
    const label = (select.getAttribute("aria-label") || "").toLowerCase();
    const texts = Array.from(select.options || [])
      .map(o => (o.textContent || "").toLowerCase())
      .join(" ");

    if (label.includes("suivi") || label.includes("prise en charge") ||
        texts.includes("prise en charge")) {
      return "Suivi";
    }
    if (label.includes("facture") || texts.includes("facture")) {
      return "Facture";
    }
    return "PDF";
  }

  function inlineUrl(url) {
    const u = new URL(url, window.location.href);
    u.searchParams.set("inline", "1");
    return u.toString();
  }

  function addPrintButton(select) {
    if (!select || select.dataset.woprPrintReady === "1") return;

    const pdfUrl = frenchPdfUrl(select);
    if (!pdfUrl) return;

    const kind = pdfKind(select);
    if (kind === "PDF") return;

    select.dataset.woprPrintReady = "1";

    const button = document.createElement("button");
    button.type = "button";
    button.className = select.classList.contains("mini-btn")
      ? "mini-btn wopr-print-pdf-btn wopr-action-open"
      : "button wopr-print-pdf-btn wopr-action-open";

    button.textContent = `🖨 ${kind}`;
    button.title = `Ouvrir le PDF ${kind.toLowerCase()} prêt à imprimer`;
    button.setAttribute("aria-label", button.title);

    button.addEventListener("click", () => {
      const target = inlineUrl(frenchPdfUrl(select));

      /*
       * V2.3.227 — certains navigateurs renvoient null avec noopener
       * même quand l'ouverture est autorisée. On utilise donc un vrai lien
       * target=_blank déclenché directement par le clic utilisateur.
       */
      const link = document.createElement("a");
      link.href = target;
      link.target = "_blank";
      link.rel = "noopener";
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
    });

    select.insertAdjacentElement("afterend", button);
  }

  function scan() {
    document.querySelectorAll("select.pdf-lang-select").forEach(addPrintButton);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scan, {once:true});
  } else {
    scan();
  }

  const observer = new MutationObserver(scan);
  observer.observe(document.documentElement, {childList:true, subtree:true});
})();
