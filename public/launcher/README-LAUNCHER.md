# Prototype lanceur WOPR unifié

Ce prototype ne remplace pas encore les anciens lanceurs.

Fonctions :
- DÉMARRER WOPR
- OUVRIR WOPR si déjà actif
- ARRÊTER WOPR
- PID unique pour éviter les doubles instances
- création du venv et vérification des dépendances
- affichage de la date et de la taille de `private/data/foulfix.db`
- logs dans `private/data/`

Fermer la fenêtre du lanceur ne coupe pas WOPR.

Build Windows :
`public/scripts/build_wopr_launcher_windows.ps1`
=> `public/launcher/dist/WOPR.exe`

Build Linux :
`chmod +x public/scripts/build_wopr_launcher_linux.sh`
`public/scripts/build_wopr_launcher_linux.sh`
=> `public/launcher/dist/WOPR`
