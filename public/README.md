# WOPR — cœur public

Version documentée : **2.3.285**.

Ce dossier contient le code public de WOPR. Les bases, documents clients, clés, jetons, paramètres et personnalisations restent dans `../private/` et ne doivent pas être publiés.

## Architecture
- `app.py` : application Flask
- `templates/` : HTML/Jinja
- `static/` : CSS, JavaScript et ressources
- `launcher/` : lanceur unifié
- `requirements.txt` : dépendances

Le thème 8-BIT applique aussi son rendu aux actions ajoutées dynamiquement.

## Licence et plateformes
WOPR est distribué gratuitement par Foul-Fix et publié sous licence GNU GPLv3.
Linux et Windows sont supportés ; macOS n’est pas supporté.
