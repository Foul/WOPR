# WOPR - Manuel utilisateur

**Workflow d’Organisation et de Pilotage des Réparations**  
Version documentée : **2.3.194**  
Documentation mise à jour : **7 septembre 2026**

> Développé par Foul-Fix, avec l’aide de ChatGPT (OpenAI) pour l’assistance au développement, à la documentation et aux tests.

---

## 1. Présentation

WOPR signifie **Workflow d’Organisation et de Pilotage des Réparations**.

WOPR est une application locale de gestion d’atelier destinée à centraliser le cycle complet d’une réparation : réception du matériel, suivi, client, devis, facture, encaissement, restitution, documents, contacts, achats, justificatifs et suivi administratif.

Cette documentation correspond à la version **2.3.194** du paquet public fourni. Elle est volontairement indépendante de l’application : elle peut être publiée sur GitHub, sur un site web, ou distribuée sous forme de PDF.

> Développé par Foul-Fix, avec l’aide de ChatGPT (OpenAI) pour l’assistance au développement, à la documentation et aux tests.

## 2. Principes importants

- WOPR fonctionne comme une application web locale, avec une interface dans le navigateur.
- Les données métier sont séparées du code public dans le dossier `private/`.
- **L’identité de l’entreprise est privée et configurable** : nom commercial, responsable, coordonnées, informations légales, logo de facture et paramètres de messagerie ne sont pas codés en dur dans le cœur public.
- Un dépôt public ne doit jamais contenir `private/`, la base SQLite, les sauvegardes, les clés, les jetons, les signatures ou les documents clients.
- Les documents gérés par WOPR sont organisés dans la partie privée : Factures, Devis et Suivi de réparation.
- Le **Suivi** est la source de vérité pour le chiffre d’affaires et les montants comptables. Les PDF restent des justificatifs et ne sont pas relus pour recalculer le CA.
- Les fonctions optionnelles (Google Contacts, Abby, SMTP Proton, KDE Connect) peuvent être utilisées uniquement si elles sont configurées.

## 3. Démarrage et installation

### Prérequis

WOPR utilise Python 3 et les dépendances déclarées dans `public/requirements.txt`, notamment Flask, ReportLab, qrcode, cryptography et les bibliothèques Google nécessaires à la synchronisation des contacts.

### Linux

Le paquet fournit `WOPR.desktop` et `Arreter-WOPR.desktop`. Le lanceur appelle les scripts de démarrage présents dans `public/scripts/` et ouvre l’application locale dans le navigateur.

### Windows

Le paquet fournit `WOPR-Windows.cmd` / `WOPR-Windows.vbs` ainsi que leurs équivalents d’arrêt. Les lanceurs utilisent PowerShell et les scripts contenus dans `public/scripts/`. Le lancement affiche une fenêtre de progression pendant l’initialisation, bloque les doubles démarrages et ouvre le navigateur uniquement lorsque WOPR répond. Les messages et pages HTML utilisent explicitement UTF-8 sous Windows.

### Accès local

Une fois WOPR démarré, l’interface est accessible localement, habituellement sur :

`http://127.0.0.1:5000`

Au premier lancement, WOPR initialise les éléments locaux nécessaires. Le PIN administrateur et la clé maître doivent être protégés avec soin.

## 4. Navigation générale

La barre principale regroupe les accès suivants :

- **Atelier** : tableau de bord synthétique.
- **Recherche** : recherche globale en lecture rapide.
- **Nouvelle réparation** : création d’un nouveau dossier.
- **Facture simple** : facture sans dossier de réparation classique.
- **Suivi** : vue chronologique et comptable des réparations.
- **Factures** : liste et gestion des factures.
- **Devis** : création, modification et envoi des devis.
- **Clients** : carnet clients, imports/exports et historique.
- **Achats / Ventes** : opérations et justificatifs.
- **Antivirus** : suivi des licences et renouvellements.
- **Abby** : connexion et synchronisation avec Abby.
- **Sécurité** : PIN, sauvegardes, SMTP, logo facture et portabilité.
- **CA / Déclarations** : synthèse du chiffre d’affaires.
- **Verrouiller** : retour en mode protégé.

L’interface propose quatre thèmes mémorisés localement dans le navigateur : **Normal**, **Dark**, **WOPR / Terminal** et **8-bit**. Le thème Dark privilégie un affichage sombre moderne ; le thème WOPR / Terminal utilise une présentation noire et vert phosphore tout en conservant les couleurs métier importantes. La navigation reste responsive et se réorganise automatiquement sur les écrans portables ou avec une mise à l’échelle Windows élevée.

## 5. Tableau de bord Atelier

La page **Atelier** est la vue d’accueil opérationnelle. Elle permet de voir immédiatement :

- le nombre de dossiers en cours ;
- les réparations en attente de pièce ;
- les dossiers encore actifs reçus depuis 14 jours ou plus, avec leur ancienneté ;
- les matériels terminés à restituer ;
- les factures impayées et leur montant ;
- le chiffre d’affaires encaissé du mois ;
- le nombre de réparations entrées dans le mois ;
- les matériels terminés depuis 7 jours ou plus ;
- les règlements encore en attente ;
- les derniers dossiers modifiés.

Les cartes servent de raccourcis vers les vues détaillées correspondantes.

## 6. Nouvelle réparation et dossier atelier

### Création

**Nouvelle réparation** crée un dossier client/atelier. Selon les informations disponibles, WOPR peut associer un client existant ou créer les éléments nécessaires.

Le dossier peut contenir notamment :

- identité et coordonnées du client ;
- date de réception ;
- appareil et problème déclaré ;
- état d’avancement ;
- informations techniques ;
- mot de passe système, protégé lorsqu’il est utilisé ;
- montants de prestation et de marchandise ;
- modalités de remise ou d’envoi ;
- remarques ;
- suivi de statut ;
- signature client et documents PDF associés.

### Statuts atelier

WOPR distingue les états de travail tels que Reçu, Diagnostic, En attente accord, En attente pièce, En réparation, Terminé et Restitué. Les vues Atelier et Suivi utilisent ces états pour filtrer et attirer l’attention sur les dossiers importants.

### Fiche réparation

La fiche permet de consulter le dossier, modifier le suivi, facturer, modifier une facture existante, générer/envoyer le suivi et communiquer avec le client.

## 7. Suivi des réparations

Le **Suivi** est la vue centrale des réparations. Il présente les dossiers par année et par mois et permet notamment :

- de rechercher un client ou un dossier ;
- de filtrer les matériels à restituer ;
- d’ouvrir directement un dossier ;
- de modifier une ligne ;
- de facturer un dossier ;
- d’accéder à la facture ;
- de suivre l’encaissement réel ;
- d’exporter le suivi en CSV.

Les couleurs ont un rôle métier : une ligne ou cellule peut signaler une facturation/affectation comptable particulière ou un règlement en attente.

**Règle comptable essentielle :** le CA officiel provient des champs comptables du Suivi. Les PDF ne sont pas analysés pour produire les montants.

## 8. Facturation

### Facture liée à une réparation

Depuis un dossier, WOPR permet de préparer la facture avec des lignes de prestation et de marchandise, puis de générer le PDF.

Une facture existante peut être modifiée sans recréer un nouveau dossier de réparation.

### Facture simple

La page **Facture simple** sert à établir une facture sans passer par un dossier de réparation complet. Elle accepte des lignes de prestation et de marchandise.

### Liste des factures

La page **Factures** propose une recherche, l’ouverture d’une facture, sa modification et son envoi.

### PDF multilingues

Les PDF de facture et de prise en charge peuvent être générés dans plusieurs langues : français, anglais, ukrainien, espagnol, allemand et italien. L’interface WOPR reste en français.

### Envoi

Si le SMTP est configuré, WOPR peut préparer et envoyer les factures par e-mail. Un lien/message peut également être préparé pour un envoi au client.

## 9. Devis

La section **Devis** permet :

- de créer un devis ;
- d’ajouter des lignes de prestation et de marchandise ;
- de modifier un devis existant ;
- de générer son PDF ;
- d’ouvrir les documents originaux associés lorsqu’ils existent ;
- d’envoyer le devis par e-mail ;
- de supprimer un devis.

Les devis sont conservés séparément des factures et restent rattachables au client concerné.

## 10. Clients et contacts

La page **Clients** centralise les coordonnées et les informations de contact.

Fonctions disponibles :

- recherche de clients ;
- modification et suppression d’une fiche ;
- gestion personne ou entreprise ;
- notes client ;
- historique complet des réparations, factures et devis ;
- détection/fusion de doublons sûrs ;
- import Google CSV ;
- import Proton VCF ;
- export Google CSV ;
- export Proton CSV ;
- export VCard universel ;
- connexion et synchronisation Google Contacts ;
- préparation de messages client.

L’historique client regroupe les éléments utiles pour retrouver rapidement dossiers, factures, devis et situations à surveiller.

La fiche d’historique affiche désormais immédiatement :
- le nombre de dossiers, factures et devis ;
- la dernière intervention réelle connue ;
- un accès direct au dernier dossier, à la dernière facture et au dernier devis ;
- les montants cumulés et les éventuels éléments à surveiller.

## 11. Recherche globale

La page **Recherche** permet une recherche transversale dans plusieurs types de données :

- clients ;
- réparations ;
- achats / ventes ;
- devis.

Les résultats proposent des raccourcis vers la fiche ou la page concernée. Cette vue est destinée à retrouver rapidement une information sans modifier les données directement.

## 12. Achats / Ventes et justificatifs

La section **Achats / Ventes** enregistre les opérations par année et fournit des totaux synthétiques.

Elle permet :

- d’ajouter une opération ;
- de rechercher dans les opérations ;
- de modifier une ligne directement ;
- de supprimer une ligne ;
- de joindre un justificatif fournisseur ;
- d’ouvrir le justificatif d’un achat ;
- d’ouvrir la facture client correspondante pour une vente ;
- de contrôler les liens de justificatifs cassés ;
- de consulter les archives annuelles.

Les factures fournisseurs peuvent être PDF, XML ou image selon les cas. Les fichiers déjà classés sont conservés et WOPR privilégie les rattachements sûrs plutôt que les doublons ou les rapprochements approximatifs.

**Important :** les chiffres de vente et le CA affichés officiellement viennent du Suivi. Les justificatifs ne modifient jamais le CA.

## 13. Abby

L’intégration **Abby** est optionnelle.

Elle permet notamment :

- d’enregistrer la configuration API ;
- de tester la connexion ;
- de synchroniser les clients vers Abby ;
- de consulter les erreurs récentes ;
- d’importer des factures fournisseurs électroniques XML dans Achats / Ventes ;
- de détecter les doublons lors de l’import.

La clé API est un secret local. Elle ne doit jamais être publiée dans GitHub, dans la documentation ou dans une archive publique.

## 14. Antivirus

La page **Antivirus** sert de petit registre de licences/abonnements.

Pour chaque ligne, WOPR peut mémoriser :

- le client ;
- la date de mise en place ;
- le produit antivirus ;
- la date d’expiration ;
- le numéro de facture ;
- une information de licence ou remarque.

Des compteurs indiquent les licences valides, celles à renouveler dans les 30 jours et celles expirées.

L’édition se fait **directement dans la ligne** : **✏️ Éditer** active les champs, **✓ Valider** enregistre, **Annuler** abandonne les changements et **Supprimer** efface la ligne après confirmation.

## 15. CA / Déclarations

La page **CA / Déclarations** présente les montants nécessaires au suivi du chiffre d’affaires et aux déclarations.

Les valeurs automatiques proviennent du Suivi des réparations et des champs comptables associés. La page peut permettre des ajustements/valeurs enregistrées selon l’année, sans utiliser les PDF comme source de calcul.

Pour éviter toute incohérence, le principe à retenir est simple : **un seul référentiel de CA = le Suivi**.

## 16. Communication client

WOPR peut préparer différents messages à destination du client :

- suivi de réparation ;
- facture ;
- devis ;
- message libre lié à un dossier ou à une fiche client.

Selon la configuration de la machine, l’envoi peut utiliser :

- Proton SMTP pour l’e-mail ;
- KDE Connect pour l’envoi de SMS depuis un appareil compatible ;
- un message prêt à copier/coller vers un autre service.

Les fonctions externes restent optionnelles : WOPR reste utilisable sans elles.

## 17. Sécurité locale

La page **Sécurité** regroupe les éléments sensibles de l’installation.

### PIN administrateur

Le PIN protège l’accès atelier. Il est stocké sous forme de hash et la session d’administration est limitée dans le temps.

### Clé maître

Les secrets locaux sont chiffrés. La clé maître doit être conservée avec soin : sans elle, les secrets chiffrés ne sont plus exploitables.

### Mot de passe système des appareils

Lorsqu’un mot de passe est stocké pour une réparation, il n’est pas affiché directement dans le HTML. Sa révélation passe par une action protégée.

### Sauvegardes

WOPR crée une sauvegarde SQLite automatique quotidienne et conserve les sauvegardes récentes. Une sauvegarde manuelle peut également être déclenchée.

### SMTP

Les paramètres Proton SMTP et le jeton restent locaux.

### Logo des factures

Le logo d’entreprise choisi par l’utilisateur est enregistré dans `private/assets/`, jamais dans la partie publique. Il peut être remplacé ou supprimé depuis Sécurité.

### Portabilité

Le diagnostic de portabilité contrôle notamment la présence du cœur public, la structure privée, les droits d’écriture et les lanceurs.

## 18. Organisation des données

Dans une installation complète, WOPR sépare le code et les données.

Structure simplifiée :

```text
WOPR/
├── WOPR.desktop
├── Arreter-WOPR.desktop
├── WOPR-Windows.cmd / .vbs
├── Arreter-WOPR-Windows.cmd / .vbs
├── public/
│   ├── app.py
│   ├── requirements.txt
│   ├── templates/
│   ├── static/
│   └── scripts/
└── private/                 # JAMAIS dans un dépôt public
    ├── data/
    ├── documents/
    │   ├── Devis/
    │   ├── Factures/
    │   └── Suivi de réparation/
    ├── signatures/
    ├── assets/
    └── seeds/
```

Le nom interne de certains fichiers ou variables peut conserver une ancienne terminologie pour compatibilité. Cela ne signifie pas que ces éléments doivent être publiés.

## 19. Publication sur GitHub

Avant toute publication, vérifier impérativement qu’aucune donnée privée n’est incluse. Le cœur public doit rester **générique** : les valeurs d’entreprise réelles proviennent de la configuration locale et `Foul-Fix` n’apparaît publiquement que dans le crédit de développement ou dans une compatibilité technique explicitement historique.

### À publier

- le code public WOPR ;
- les templates et ressources génériques ;
- les scripts de lancement ;
- `requirements.txt` ;
- la documentation publique ;
- un `.gitignore` adapté.

### À ne jamais publier

- `private/` ;
- `*.db` et sauvegardes SQLite ;
- `master.key` ;
- clés API et jetons ;
- identifiants OAuth Google ;
- signatures ;
- factures, devis, suivis réels ;
- exports clients ;
- captures contenant noms, téléphones, adresses, montants privés ou autres données réelles.

Le pack fourni inclut un `.gitignore` recommandé pour compléter celui de l’application.

### Licence

Aucune licence logicielle n’est choisie automatiquement par cette documentation. Avant de rendre le dépôt réellement open source, ajouter la licence correspondant au choix de Foul-Fix.

## 20. Hébergement de la documentation sur un site

Le dossier `docs/` fourni est statique et peut être hébergé indépendamment de WOPR.

Exemple :

`https://ton-site.example/wopr/`

Il suffit de déposer dans ce répertoire :

- `index.html` ;
- `WOPR-Manuel.pdf` ;
- le dossier `images/`.

Aucun Python, Flask ou accès à la base WOPR n’est nécessaire pour afficher la documentation.

La même documentation peut être utilisée avec GitHub Pages : le fichier HTML est autonome et ne dépend d’aucun service externe.

## 21. Politique de mise à jour de la documentation

À partir de cette version, une modification fonctionnelle de WOPR doit entraîner la vérification de la documentation.

Pour chaque correction ou évolution :

1. identifier la page ou la fonction concernée ;
2. corriger `docs/manuel.md` ;
3. corriger `docs/index.html` ;
4. régénérer `docs/WOPR-Manuel.pdf` si l’information est visible pour l’utilisateur ;
5. ajouter une ligne dans `docs/CHANGELOG-DOC.md` ;
6. vérifier qu’aucune donnée privée n’a été introduite.

Les changements purement internes sans impact utilisateur peuvent être consignés dans le changelog sans alourdir le manuel.

## 22. Dépannage rapide

### WOPR ne démarre pas

- vérifier que Python 3 est installé ;
- vérifier que les dépendances de `requirements.txt` sont installées ;
- utiliser le lanceur correspondant au système ;
- consulter les messages du script de démarrage si nécessaire.

### Une fonction Google/Abby/SMTP ne marche pas

Ces intégrations sont optionnelles et nécessitent leur propre configuration. Vérifier d’abord les identifiants locaux et le test de connexion de la page concernée.

### Un justificatif ne s’ouvre plus

Utiliser **Achats / Ventes → Vérifier les justificatifs liés** pour identifier les liens cassés. Éviter de renommer/déplacer des fichiers en dehors de WOPR sans mettre à jour leur rattachement.

### Le CA paraît incohérent

Contrôler les données du **Suivi** et les dates d’encaissement. Ne pas essayer de corriger le CA en modifiant un PDF.

### Perte de clé maître

Une clé maître perdue ne peut pas être reconstituée à partir de la documentation. Conserver une sauvegarde sécurisée de cette clé en dehors du dépôt public.

## 23. Crédit

**Développé par Foul-Fix, avec l’aide de ChatGPT (OpenAI) pour l’assistance au développement, à la documentation et aux tests.**

WOPR est développé comme un outil métier de terrain, avec une priorité donnée à la simplicité d’utilisation, à la portabilité et à la conservation locale des données sensibles.


### Devis historiques

Lors de l'ouverture de l'historique d'un client, WOPR peut retrouver d'anciens devis créés avant la liaison systématique par identifiant client. Un devis sans `client_id` est rattaché automatiquement uniquement si son nom correspond sans ambiguïté à une seule fiche client. Les formes `Prénom Nom` et `Nom Prénom` sont reconnues.
