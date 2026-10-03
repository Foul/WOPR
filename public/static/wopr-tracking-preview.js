(function(){
  "use strict";

  function addTrackingPreviewButton(){
    const codeBox = document.querySelector(".tracking-code-inline");
    const adminActions = document.querySelector(".dossier-actions");
    if (!codeBox || !adminActions || codeBox.querySelector(".wopr-tracking-preview-btn")) return;

    const match = window.location.pathname.match(/^\/repair\/(\d+)\/?$/);
    if (!match) return;

    const link = document.createElement("a");
    link.className = "button wopr-action-open wopr-tracking-preview-btn";
    link.href = "/repair/" + encodeURIComponent(match[1]) + "/tracking-preview";
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "👁 Aperçu sans compteur";
    link.title = "Ouvrir le suivi public sans enregistrer cette consultation";

    codeBox.appendChild(document.createTextNode(" "));
    codeBox.appendChild(link);
  }



  function placeFlashToast(){
    const flash = document.getElementById("woprFlash");
    if (!flash) return;

    const header = document.querySelector("header.topbar, .topbar");
    const bottom = header ? Math.ceil(header.getBoundingClientRect().bottom) : 0;

    flash.style.position = "fixed";
    flash.style.top = Math.max(12, bottom + 12) + "px";
    flash.style.left = "50%";
    flash.style.transform = "translateX(-50%)";
    flash.style.zIndex = "100000";
    flash.style.width = "min(94vw, 1100px)";
    flash.style.maxWidth = "1100px";
    flash.style.margin = "0";
    flash.style.padding = "12px 48px 12px 16px";
    flash.style.lineHeight = "1.35";
    flash.style.whiteSpace = "normal";
    flash.style.color = "#163624";
    flash.style.background = "#e8fff0";
    flash.style.border = "1px solid #8ed3a1";
    flash.style.boxShadow = "0 8px 24px rgba(0,0,0,.22)";

    const close = document.getElementById("woprFlashClose");
    if (close) {
      close.style.position = "absolute";
      close.style.right = "10px";
      close.style.top = "50%";
      close.style.transform = "translateY(-50%)";
    }
  }

  function initWoprTrackingHelpers(){
    addTrackingPreviewButton();
    placeFlashToast();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initWoprTrackingHelpers, {once:true});
  } else {
    initWoprTrackingHelpers();
  }

  window.addEventListener("resize", placeFlashToast);
})();
