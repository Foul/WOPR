# WOPR 2.5.0

## Release stable — 25 septembre 2026

Cette release renforce la sécurité locale de WOPR, stabilise son fonctionnement Linux / Windows et corrige plusieurs défauts d'interface du thème 8-BIT.

### SQLCipher et sécurité
- La base principale `private/data/wopr.db` est désormais chiffrée avec SQLCipher.
- La clé de base est aléatoire et distincte du PIN administrateur.
- Linux et Windows utilisent la même base de code avec des dépendances SQLCipher adaptées à chaque plateforme.
- Le crash natif Windows lié à `PRAGMA cipher_memory_security = ON` est corrigé.

### Launcher
- Le PIN SQLCipher est conservé uniquement en mémoire vive pendant la session du launcher.
- Le même PIN peut être réutilisé à l'arrêt pour la sauvegarde sans seconde saisie dans une session normale.
- Aucun PIN SQLCipher n'est écrit sur disque.
- Les binaires Linux et Windows déjà compilés restent valides tant que `wopr_launcher.py` n'a pas été modifié depuis leur compilation.

### Sauvegardes
- Les sauvegardes externes sont adaptées à la base chiffrée.
- La rétention Proton Drive et Freebox est fixée à 15 jours.
- Les fichiers `.sha256` associés sont supprimés avec les archives expirées.

### Interface
- La topbar du thème 8-BIT est stabilisée sur les affichages haute résolution et avec mise à l'échelle.
- Le chevauchement entre Recherche et Suivi est corrigé.
- La disposition ne dépend plus uniquement de seuils arbitraires de résolution.

### Structure
- Les ressources publiques restent dans `public/static/`.
- Les ressources propres à chaque installation restent dans `private/assets/`.
- L'ancien dossier vide `public/assets/` peut être supprimé.

Cette version reste officiellement supportée sous Linux et Windows. macOS reste non supporté : aucun binaire officiel, aucun test de compatibilité et aucun support garanti.
