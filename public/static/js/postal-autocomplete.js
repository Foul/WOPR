(() => {
  const inputs = [...document.querySelectorAll('[data-postal-autocomplete]')];
  if (!inputs.length) return;

  const cache = new Map();

  const loadDatabase = async (url) => {
    if (!cache.has(url)) {
      cache.set(url, fetch(url, {cache: 'force-cache'}).then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      }));
    }
    return cache.get(url);
  };

  const suggestionContainer = (postalInput) =>
    postalInput.closest('form') ||
    postalInput.closest('[data-client-row]') ||
    postalInput.parentElement ||
    document;

  const removeSuggestions = (postalInput) => {
    const root = suggestionContainer(postalInput);
    const existing = root.querySelector(
      `[data-postal-suggestions-for="${postalInput.id}"]`
    );
    if (existing) existing.remove();
  };

  const addSuggestions = (postalInput, cityInput, cities) => {
    removeSuggestions(postalInput);
    if (cities.length <= 1) return;

    const select = document.createElement('select');
    select.className = 'postal-city-suggestions';
    select.dataset.postalSuggestionsFor = postalInput.id;
    select.style.marginTop = '.4rem';

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = `— Choisir la ville (${cities.length} communes) —`;
    select.appendChild(placeholder);

    cities.forEach(city => {
      const option = document.createElement('option');
      option.value = city;
      option.textContent = city;
      select.appendChild(option);
    });

    select.addEventListener('change', () => {
      if (!select.value) return;
      cityInput.value = select.value;
      cityInput.dataset.postalAutofilled = '1';
      select.remove();
      cityInput.dispatchEvent(new Event('change', {bubbles: true}));
    });

    cityInput.insertAdjacentElement('afterend', select);
  };

  inputs.forEach(postalInput => {
    const cityId = postalInput.dataset.cityTarget;
    const dataUrl = postalInput.dataset.postalData;
    const cityInput = document.getElementById(cityId);
    if (!cityInput || !dataUrl) return;

    cityInput.addEventListener('input', () => {
      cityInput.dataset.postalAutofilled = '0';
    });

    const updateCity = async () => {
      const cp = postalInput.value.replace(/\D/g, '').slice(0, 5);
      if (postalInput.value !== cp) postalInput.value = cp;

      removeSuggestions(postalInput);
      if (cp.length !== 5) return;

      try {
        const database = await loadDatabase(dataUrl);
        const cities = database[cp] || [];
        if (!cities.length) return;

        if (cities.length === 1) {
          if (!cityInput.value.trim() || cityInput.dataset.postalAutofilled === '1') {
            cityInput.value = cities[0];
            cityInput.dataset.postalAutofilled = '1';
            cityInput.dispatchEvent(new Event('change', {bubbles: true}));
          }
          return;
        }

        // Plusieurs communes : jamais de choix arbitraire.
        if (cityInput.dataset.postalAutofilled === '1') {
          cityInput.value = '';
          cityInput.dataset.postalAutofilled = '0';
        }
        addSuggestions(postalInput, cityInput, cities);
      } catch (error) {
        console.warn('WOPR : base locale des codes postaux indisponible.', error);
      }
    };

    postalInput.addEventListener('input', updateCity);
    postalInput.addEventListener('change', updateCity);
    postalInput.setAttribute('inputmode', 'numeric');
    postalInput.setAttribute('maxlength', '5');
  });
})();
