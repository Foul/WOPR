# Changelog de la documentation

## 6 septembre 2026 - documentation 2.3.192

- reconstruction complète à partir du ZIP public WOPR 2.3.192 ;
- inventaire des pages et fonctions présentes dans le code ;
- ajout du fonctionnement Antivirus : `✏️ Éditer` / `✓ Valider` ;
- ajout de la gestion du logo facture dans la partie privée ;
- ajout des consignes GitHub et d’hébergement statique ;
- aucune donnée issue de `private/` ni aucune capture client réelle incluse.

## 2.3.194 - 7 septembre 2026 - support Windows
- Fiabilisation du lanceur Windows : fenêtre de progression visible, verrou anti-double lancement et ouverture du navigateur uniquement lorsque WOPR est prêt.
- Les dépendances Python ne sont plus réinstallées inutilement à chaque démarrage ; elles sont contrôlées via l’empreinte de `requirements.txt`.
- Séparation des logs standard et erreur du serveur Windows pour éviter les échecs silencieux de `Start-Process`.
- Correction de l’encodage des lanceurs et messages Windows ; PowerShell 7 est préféré lorsqu’il est disponible.
- Forçage UTF-8 des réponses HTML afin d’éviter les caractères accentués corrompus sous Windows.
- Navigation responsive en mode normal et 8-bit pour les écrans portables et les affichages avec mise à l’échelle élevée.

## 2.3.193 - 6 septembre 2026 - nettoyage publication publique
- Suppression des coordonnées et identifiants d’entreprise codés en dur dans le cœur public.
- Les e-mails, SMS, devis et factures utilisent désormais l’identité configurée localement.
- Le groupe Google Contacts utilise le réglage local avec `WOPR` comme valeur neutre.
- La clé maître utilise le nouvel emplacement WOPR tout en conservant la compatibilité avec l’ancien emplacement Foul-Fix pour les installations existantes.
- Foul-Fix reste mentionné uniquement au crédit de développement et pour cette compatibilité historique.
