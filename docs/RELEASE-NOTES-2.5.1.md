# WOPR 2.5.1

## Release de maintenance - 25 septembre 2026

WOPR 2.5.1 finalise la série 2.5.x après la publication du tag `v2.5.0` et aligne proprement l'ensemble de la documentation publique.

### Documentation
- `manuel.md`, `documentation.html`, `index.html` et `WOPR-Manuel.pdf` sont alignés sur **2.5.1**.
- La date de documentation est corrigée au **25 septembre 2026**.
- Les anciennes mentions 2.4.0 encore visibles dans la documentation publique sont supprimées.
- Le changelog conserve l'historique de la release 2.5.0.

### Base 2.5.x conservée
- Base principale chiffrée avec SQLCipher.
- Compatibilité Linux / Windows avec dépendances SQLCipher adaptées à chaque plateforme.
- Correctif Windows pour `cipher_memory_security`.
- PIN SQLCipher conservé uniquement en RAM pendant la session du launcher.
- Sauvegardes externes adaptées à la base chiffrée.
- Topbar 8-BIT stabilisée et chevauchement Recherche / Suivi corrigé.

Cette release ne nécessite pas de recompilation de `WOPR` ou `WOPR.exe` si les binaires actuels ont déjà été compilés à partir du `wopr_launcher.py` validé et que ce source n'a pas changé depuis.
