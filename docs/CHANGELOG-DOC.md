# Changelog de la documentation

## 2.3.214 - 10 septembre 2026 - release Linux/Windows, GPLv3 et soutien
- Finalisation du **lanceur unifié Linux/Windows** avec interface graphique et sauvegarde à l’arrêt.
- Ajout des binaires officiels **`WOPR` pour Linux** et **`WOPR.exe` pour Windows**.
- Suppression des anciens lanceurs `.desktop`, `.cmd`, `.vbs` et scripts de lancement devenus inutiles.
- WOPR est désormais publié sous licence **GNU GPLv3**.
- Ajout explicite de la mention **100 % gratuit et open source**.
- Linux et Windows sont indiqués comme plateformes supportées.
- macOS est explicitement indiqué comme **non supporté** : aucun binaire officiel, aucun test et aucun support garanti.
- Ajout d’un bloc de soutien facultatif via PayPal (`paypal.me/foul`) et du QR code associé.
- Ajout de `docs/LICENCE-SUPPORT.md` et du guide `GITHUB-PUBLICATION.md`.
- Aucun don n’est requis et aucune fonctionnalité de WOPR n’est réservée aux donateurs.

## 2.3.210 - 9 septembre 2026 - release
- Ajout de l’autocomplétion locale des villes par code postal dans la création et la modification d’un suivi.
- Utilisation de la base postale officielle avec les libellés de communes INSEE 2026 correctement accentués et capitalisés.
- Lorsqu’un code postal dessert plusieurs communes, WOPR propose la liste correspondante sans choix arbitraire.
- Documentation HTML et PDF alignée sur la version 2.3.210.

## 2.3.209 - 9 septembre 2026 - gestion des archives clients
- Ajout d’un accès visible aux **Clients archivés** depuis la page Clients.
- Ajout d’un retour direct vers les clients actifs depuis les archives.
- La suppression définitive d’un client archivé est toujours accessible après confirmation renforcée.

## 2.3.208 - 9 septembre 2026 - suppression volontaire des fiches de test
- Ajout d’une suppression définitive réservée aux fiches de test ou créées par erreur.
- La suppression totale peut effacer le client et son historique local associé après sauvegarde et confirmation explicite.
- L’archivage reste le comportement normal pour un vrai client ayant un historique.

## 2.3.207 - 9 septembre 2026 - recherche client et remarques du suivi
- Recherche progressive d’un client existant lors de la création d’un suivi à partir du début du prénom, du nom ou de l’entreprise.
- La liste n’affiche que les correspondances utiles au lieu de présenter tout le carnet clients.
- Les remarques restent réservées au suivi de réparation et sont retirées de l’éditeur de facture.
- Modifier une facture conserve les remarques déjà présentes dans le suivi.

## 2.3.206 - 9 septembre 2026 - sélection d’un client existant
- Ajout de la sélection explicite d’un client existant lors de la création d’un suivi.
- Les coordonnées de la fiche sélectionnée sont reprises automatiquement.
- Les clients archivés ne sont pas proposés.

## 2.3.205 - 9 septembre 2026 - archivage clients
- Les clients possédant un historique peuvent être archivés sans supprimer leurs suivis, factures ou devis.
- Un client archivé peut être restauré.
- Les clients archivés sont exclus des sélections et synchronisations courantes.

## 2.3.204 - 9 septembre 2026 - entreprise et date de facture
- Prise en charge du nom d’entreprise dans la création et la modification d’un suivi, ainsi que dans les documents concernés.
- Affichage compact de l’entreprise dans la fiche de suivi.
- La date de facture est désormais modifiable depuis **Facture / Modifier facture** sans modifier automatiquement le numéro de facture.

## 2.3.203 - 9 septembre 2026 - release
- Recherche globale directement accessible depuis la barre supérieure.
- Recherche multi-mots, insensible aux accents, à la casse et à la ponctuation.
- Historique client enrichi avec accès rapide aux derniers dossiers, factures et devis.
- Rattachement sécurisé des devis historiques lorsqu'une correspondance client est non ambiguë.
- Tableau de bord Atelier enrichi avec les dossiers actifs de plus de 14 jours.
- Ajout des thèmes Dark et WOPR Terminal et améliorations du thème 8-bit.
- Optimisation de la synchronisation Google Contacts et gestion du quota.
- Ajustements d'ergonomie, de sécurité et de fiabilité.
- Documentation HTML et PDF alignée sur la version 2.3.203.

## 2.3.202 - 8 septembre 2026 - devis historiques rattachés aux clients
- L'historique client retrouve désormais les anciens devis créés sans `client_id`.
- Le rattachement automatique n'est effectué que lorsque le nom du devis correspond de façon non ambiguë à une seule fiche client.
- Les variantes `Prénom Nom` et `Nom Prénom` sont reconnues.

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
