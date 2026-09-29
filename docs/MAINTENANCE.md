# Maintenance de la documentation WOPR

Version de référence actuelle : **2.6.0**.

À chaque évolution visible :
1. mettre à jour `manuel.md` ;
2. mettre à jour `documentation.html` ;
3. mettre à jour `index.html` si nécessaire ;
4. régénérer `WOPR-Manuel.pdf` ;
5. ajouter une section `## APP_VERSION` dans `CHANGELOG-DOC.md` ;
6. vérifier l’absence de données privées ;
7. vérifier les visuels publics, dont le QR code PayPal.

Le script de release extrait ses notes depuis `docs/CHANGELOG-DOC.md`.

`Update-WOPR.sh` doit bloquer la publication si :
- la version courante n’est pas cohérente entre l’application et la documentation ;
- `docs/WOPR-Manuel.pdf` est plus ancien que `docs/manuel.md` ;
- un fichier `docs/RELEASE-NOTES-*.md` est encore présent ;
- un visuel obligatoire de la documentation est manquant.
