(() => {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  if (params.get("sync_watch") !== "1") return;

  let finished = false;

  function toast(text, type) {
    let box = document.getElementById("wopr-google-sync-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "wopr-google-sync-toast";
      Object.assign(box.style, {
        position: "fixed",
        right: "18px",
        bottom: "18px",
        zIndex: "10000",
        maxWidth: "430px",
        padding: "14px 16px",
        borderRadius: "8px",
        fontWeight: "700",
        boxShadow: "0 4px 18px rgba(0,0,0,.28)",
        border: "1px solid #7a8a96"
      });
      document.body.appendChild(box);
    }

    box.style.background = type === "error" ? "#fff1f1" : "#ecfff1";
    box.style.color = type === "error" ? "#8f1414" : "#145c27";
    box.style.borderColor = type === "error" ? "#d77" : "#79bd8a";
    box.textContent = text;
  }

  async function check() {
    if (finished) return;

    try {
      const response = await fetch("/contacts/sync-google/status", {
        cache: "no-store",
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error("HTTP " + response.status);

      const s = await response.json();

      if (s.running) {
        toast(`Google : synchronisation en cours… ${s.done || 0}/${s.total || 0}`, "ok");
        setTimeout(check, 900);
        return;
      }

      finished = true;

      const errors = Number(s.errors || 0);
      const ok = Number(s.ok || 0);

      if (errors) {
        toast(`Synchronisation Google terminée : ${ok} OK · ${errors} erreur(s).`, "error");
      } else {
        toast(`✓ Synchronisation Google terminée : ${ok} contact(s) synchronisé(s).`, "ok");
      }

      setTimeout(() => {
        const clean = new URL(window.location.href);
        clean.searchParams.delete("sync_watch");
        window.location.replace(clean.toString());
      }, 1300);

    } catch (e) {
      setTimeout(check, 1500);
    }
  }

  toast("Google : synchronisation en cours…", "ok");
  check();
})();
