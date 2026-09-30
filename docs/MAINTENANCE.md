# Maintenance de la documentation WOPR

Version de référence actuelle : **2.6.1**.

À chaque évolution visible :
1. mettre à jour `manuel.md` ;
2. mettre à jour `documentation.html` ;
3. mettre à jour `index.html` si nécessaire ;
4. régénérer `WOPR-Manuel.pdf` ;
5. ajouter une section `## APP_VERSION` dans `CHANGELOG-DOC.md` ;
6. vérifier l’absence de données privées ;
7. vérifier les visuels publics, dont le QR code PayPal.

Avant publication, vérifier également :
- la cohérence de la version courante entre l’application et la documentation ;
- que `docs/WOPR-Manuel.pdf` correspond bien au manuel courant ;
- qu’aucun fichier `docs/RELEASE-NOTES-*.md` obsolète n’est présent ;
- que les visuels obligatoires de la documentation sont présents.

Les notes de release sont maintenues dans `docs/CHANGELOG-DOC.md`.
