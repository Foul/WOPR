# Changelog de la documentation

## 2.3.201 - 8 septembre 2026 - historique client plus direct
- Ajout du nombre de **factures** dans le résumé client.
- La **dernière intervention** tient compte de la restitution ou de la fin du dossier avant la date d’entrée.
- Ajout d’un bloc **Accès rapide** vers le dernier dossier, la dernière facture et le dernier devis.
- Les tableaux complets restent disponibles juste en dessous.

## 2.3.200 - 8 septembre 2026 - retour Atelier après verrouillage
- Après un verrouillage manuel puis saisie du PIN, WOPR revient désormais directement sur **Atelier** au lieu de **Suivi**.

## 2.3.199 - 8 septembre 2026 - fin de l'easter egg
- La séquence finale de l'easter egg ne se ferme plus automatiquement.
- L'écran de fin reste affiché jusqu'à fermeture volontaire avec **×** ou **Échap**, afin de ne plus couper la fin de la séquence.

## 2.3.198 - 8 septembre 2026 - bouton Nouvelle réparation en thème 8-bit
- Le bouton **Nouvelle réparation** placé dans Atelier utilise désormais exactement le skin pixel-art du thème 8-bit.
- Les thèmes Normal, Dark et WOPR restent inchangés.

## 2.3.197 - 8 septembre 2026 - sauvegardes dans Sécurité
- Regroupement de **Sauvegardes** et **Sauvegarde automatique** dans une seule box.
- Le statut de la sauvegarde quotidienne, le bouton de sauvegarde manuelle et la liste des sauvegardes sont désormais réunis au même endroit.

## 2.3.196 - 8 septembre 2026 - accès Nouvelle réparation
- Suppression du doublon **Nouvelle réparation** dans la barre de navigation.
- Le bouton est conservé sur le tableau de bord **Atelier** avec le style du bouton de menu.

## 2.3.195 - 8 septembre 2026 - pilotage Atelier
- Le tableau de bord signale désormais les dossiers encore actifs depuis **14 jours ou plus**.
- Une carte affiche leur nombre immédiatement.
- Un panneau dédié liste les dossiers concernés, leur statut, leur panne et leur ancienneté.
- Les dossiers de **30 jours ou plus** sont visuellement renforcés.

## 2.3.195 - 8 septembre 2026 - thèmes d'affichage
- Ajout du thème **Dark**, sombre et moderne.
- Ajout du thème **WOPR / Terminal**, noir et vert phosphore.
- Le sélecteur permet de choisir entre Normal, Dark, WOPR / Terminal et 8-bit.
- Le choix du thème est mémorisé localement dans le navigateur.
- Les couleurs métier du Suivi restent visibles dans les nouveaux thèmes.

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
