(() => {
  const path = window.location.pathname || '';
  if (!(path === '/devis/new' || /^\/devis\/\d+\/edit$/.test(path))) return;

  const postal = document.querySelector('input[name="client_postal_code"]');
  const city = document.querySelector('input[name="client_city"]');
  if (!postal || !city) return;

  if (!postal.id) postal.id = 'quote-client-postal-code';
  if (!city.id) city.id = 'quote-client-city';

  postal.setAttribute('inputmode', 'numeric');
  postal.setAttribute('maxlength', '5');
  postal.setAttribute('data-postal-autocomplete', '');
  postal.setAttribute('data-city-target', city.id);
  postal.setAttribute('data-postal-data', '/static/data/postal_codes.json');

  const alreadyLoaded = Array.from(document.scripts).some(s =>
    (s.getAttribute('src') || '').includes('/static/js/postal-autocomplete.js')
  );

  if (!alreadyLoaded) {
    const script = document.createElement('script');
    script.src = '/static/js/postal-autocomplete.js';
    script.defer = true;
    document.body.appendChild(script);
  } else {
    // Si le script était déjà chargé avant que les attributs soient ajoutés,
    // relancer son initialisation de façon sûre via un événement DOMContentLoaded synthétique.
    document.dispatchEvent(new Event('wopr-postal-refresh'));
  }
})();
