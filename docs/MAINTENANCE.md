# Maintenance de la documentation WOPR

Version de référence actuelle : **2.3.285**.

À chaque évolution visible :
1. mettre à jour `manuel.md` ;
2. mettre à jour `documentation.html` ;
3. mettre à jour `index.html` si nécessaire ;
4. régénérer `WOPR-Manuel.pdf` ;
5. ajouter une section `## APP_VERSION` dans `CHANGELOG-DOC.md` ;
6. vérifier l’absence de données privées.

Le script de release extrait ses notes depuis `docs/CHANGELOG-DOC.md`.
