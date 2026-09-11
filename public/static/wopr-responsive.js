(function () {
  'use strict';

  let dock = null;
  let spacer = null;
  let active = null;
  let syncing = false;
  let rafPending = false;

  function createDock() {
    if (dock) return;
    dock = document.createElement('div');
    dock.className = 'wopr-xscroll-dock';
    dock.setAttribute('aria-label', 'Défilement horizontal du tableau visible');
    dock.title = 'Défilement horizontal du tableau visible';

    spacer = document.createElement('div');
    spacer.className = 'wopr-xscroll-spacer';
    dock.appendChild(spacer);
    document.body.appendChild(dock);

    dock.addEventListener('scroll', function () {
      if (!active || syncing) return;
      syncing = true;
      active.scrollLeft = dock.scrollLeft;
      syncing = false;
    });
  }

  function isScrollable(el) {
    if (!el) return false;
    return el.scrollWidth > el.clientWidth + 2;
  }

  function candidates() {
    const found = new Set();

    /* Wrappers déjà utilisés dans WOPR. */
    document.querySelectorAll(
      '.sheet-wrapper, .legacy-total-table-wrap, .table-wrapper, .table-scroll, .contacts-table-wrap'
    ).forEach(el => found.add(el));

    /*
     * Filet de sécurité : tout conteneur d'un tableau qui possède réellement
     * un overflow horizontal CSS et dépasse sa largeur.
     */
    document.querySelectorAll('table').forEach(table => {
      let el = table.parentElement;
      for (let i = 0; el && el !== document.body && i < 4; i++, el = el.parentElement) {
        const style = getComputedStyle(el);
        const ox = style.overflowX;
        if (ox === 'auto' || ox === 'scroll') {
          found.add(el);
          break;
        }
      }
    });

    return Array.from(found).filter(isScrollable);
  }

  function verticalDistance(rect) {
    const middle = window.innerHeight / 2;
    if (rect.top <= middle && rect.bottom >= middle) return 0;
    if (rect.bottom < middle) return middle - rect.bottom;
    return rect.top - middle;
  }

  function chooseActive() {
    const list = candidates();
    if (!list.length) return null;

    const visible = list
      .map(el => ({ el, rect: el.getBoundingClientRect() }))
      .filter(x => x.rect.bottom > 0 && x.rect.top < window.innerHeight);

    if (!visible.length) return null;

    visible.sort((a, b) => verticalDistance(a.rect) - verticalDistance(b.rect));
    return visible[0].el;
  }

  function bindActive(next) {
    if (active === next) {
      if (active && spacer) spacer.style.width = active.scrollWidth + 'px';
      return;
    }

    if (active) active.removeEventListener('scroll', syncFromTable);
    active = next;

    if (!active) {
      dock.classList.remove('is-visible');
      document.body.classList.remove('wopr-has-xscroll');
      return;
    }

    active.addEventListener('scroll', syncFromTable, { passive: true });
    spacer.style.width = active.scrollWidth + 'px';

    syncing = true;
    dock.scrollLeft = active.scrollLeft;
    syncing = false;

    dock.classList.add('is-visible');
    document.body.classList.add('wopr-has-xscroll');
  }

  function syncFromTable() {
    if (!active || syncing) return;
    syncing = true;
    dock.scrollLeft = active.scrollLeft;
    syncing = false;
  }

  function update() {
    rafPending = false;
    createDock();
    bindActive(chooseActive());
  }

  function requestUpdate() {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(update);
  }

  document.addEventListener('DOMContentLoaded', function () {
    createDock();
    update();

    window.addEventListener('scroll', requestUpdate, { passive: true });
    window.addEventListener('resize', requestUpdate, { passive: true });

    /* Les tableaux peuvent changer après une recherche, modification ou affichage dynamique. */
    const observer = new MutationObserver(requestUpdate);
    observer.observe(document.body, { childList: true, subtree: true, attributes: false });
  });
})();
