# WOPR - Manuel utilisateur

**Version documentée : 2.3.286**
**Documentation mise à jour : 11 septembre 2026**

**Workflow d’Organisation et de Pilotage des Réparations**

Développé par Foul-Fix, avec l’aide de ChatGPT (OpenAI) pour l’assistance au développement, à la documentation et aux tests.

---

## 1. Présentation

WOPR signifie **Workflow d’Organisation et de Pilotage des Réparations**.

WOPR est une application locale de gestion d’atelier destinée à centraliser dans une seule interface le cycle complet d’une réparation : réception du matériel, client, diagnostic, suivi technique, devis, facture, encaissement, restitution, documents, contacts, achats, justificatifs fournisseurs, licences antivirus et suivi administratif.

WOPR est né d’un besoin concret : éviter les doubles saisies, ne plus éparpiller les informations entre plusieurs fichiers et outils, retrouver immédiatement l’historique d’un client et conserver les documents au bon endroit.

WOPR fonctionne **en local**. L’application utilise un serveur Flask local et s’ouvre dans le navigateur. Le fonctionnement de base ne dépend pas d’un service cloud obligatoire.

### 1.1 Gratuit et open source

WOPR est distribué gratuitement par Foul-Fix et publié sous licence **GNU General Public License v3.0 (GPLv3)**.

Aucun paiement, abonnement ou don n’est nécessaire pour utiliser les fonctions de WOPR.

### 1.2 Plateformes

- **Linux : supporté**
- **Windows : supporté**
- **macOS : non supporté**

Pour macOS, aucun binaire officiel n’est fourni, aucun test de compatibilité n’est réalisé et aucun support de fonctionnement n’est garanti.

### 1.3 Soutenir WOPR

Le développement peut être soutenu volontairement via PayPal :

**https://paypal.me/foul**

![QR code PayPal](images/paypal-qr.png)

Le don est totalement facultatif. Il ne débloque aucune fonctionnalité, ne donne accès à aucune version Premium et n’accorde aucun avantage dans le logiciel.

---

## 2. Principes de fonctionnement

WOPR repose sur quelques règles importantes.

- Le code distribuable se trouve dans la partie publique du projet.
- Les données réelles de l’atelier sont conservées dans `private/`.
- Les informations d’entreprise sont configurables localement et ne doivent pas être codées en dur dans le coeur public.
- Le **Suivi** est la source de vérité pour les montants de chiffre d’affaires.
- Les PDF sont des justificatifs : ils ne servent pas à recalculer automatiquement le CA.
- Les fonctions externes restent optionnelles.
- Les suppressions importantes doivent être explicites.
- L’archivage est préféré à la suppression pour les vrais clients.
- Les sauvegardes sont déclenchées automatiquement ou avant certaines opérations sensibles.

Cette séparation permet de publier le code de WOPR sans publier les données clients, factures, devis, signatures, mots de passe, jetons ou sauvegardes de l’atelier.

---

## 3. Installation et démarrage

### 3.1 Prérequis

WOPR utilise Python 3 et les dépendances déclarées dans `public/requirements.txt`.

Parmi les bibliothèques utilisées figurent notamment Flask, ReportLab, qrcode, Pillow, cryptography et les composants nécessaires à Google Contacts.

### 3.2 Linux

Le paquet officiel contient un binaire `WOPR` à la racine.

Au démarrage, le lanceur :

1. vérifie l’installation ;
2. prépare l’environnement Python si nécessaire ;
3. vérifie les dépendances ;
4. évite de lancer deux fois WOPR ;
5. démarre le serveur local ;
6. attend que le serveur soit prêt ;
7. ouvre l’application dans le navigateur.

### 3.3 Windows

Le paquet officiel contient `WOPR.exe`.

Le comportement est le même que sous Linux : environnement Python, contrôle des dépendances, protection contre les doubles lancements, démarrage du serveur puis ouverture du navigateur.

### 3.4 Adresse locale

Une fois démarré, WOPR est normalement accessible sur :

`http://127.0.0.1:5000`

### 3.5 Arrêt et sauvegarde

Le lanceur permet d’arrêter proprement WOPR.

Une sauvegarde d’arrêt n’est créée que si la base a changé depuis la sauvegarde précédente. Cela évite de générer inutilement des copies identiques.

---

## 4. Interface générale et thèmes

La barre principale donne accès à :

- **Atelier**
- **Recherche globale**
- **Suivi**
- **Factures**
- **Devis**
- **Clients**
- **Achats / Ventes**
- **Antivirus**
- **Abby**
- **Sécurité**
- **CA / Déclarations**
- **Verrouiller**

La **Facture simple** reste dans la section Factures afin de ne pas dupliquer inutilement un bouton dans la barre supérieure.

### 4.1 Thèmes

WOPR propose quatre thèmes :

- **Normal**
- **Dark**
- **WOPR / Terminal**
- **8-BIT**

Le choix est mémorisé dans le navigateur.

### 4.2 Couleurs des actions

Les actions utilisent une logique commune :

| Couleur | Rôle |
| --- | --- |
| Bleu | Ouvrir, historique, PDF, impression |
| Vert | Envoyer, enregistrer, valider |
| Ambre | Modifier |
| Violet | Dossier, joindre, fusionner, action spéciale |
| Rouge | Supprimer |
| Neutre | Annuler |

### 4.3 Thème 8-BIT

La version 2.3.285 finalise le thème 8-BIT.

Les boutons d’action adoptent un rendu pixel-art cohérent, y compris les boutons créés dynamiquement par JavaScript comme certains boutons **Facture** et **Dossier**.

Les tableaux et badges reçoivent également un habillage arcade léger, sans rendre les données difficiles à lire.

---

## 5. Tableau de bord Atelier

La page **Atelier** est la vue d’accueil opérationnelle.

Elle sert à voir rapidement :

- les dossiers en cours ;
- les réparations en attente de pièce ;
- les matériels terminés à restituer ;
- les factures impayées ;
- le montant des impayés ;
- le chiffre d’affaires encaissé du mois ;
- le nombre de réparations entrées dans le mois ;
- les dossiers terminés depuis plusieurs jours ;
- les dossiers actifs anciens à relancer ;
- les derniers dossiers modifiés.

Le bouton **Nouvelle réparation** est placé directement dans cette page.

Les cartes du tableau de bord sont cliquables lorsqu’un accès détaillé existe.

---

## 6. Nouvelle réparation

### 6.1 Recherche du client

Lors de la création d’une réparation, il est possible de rechercher un client existant en saisissant le début de son prénom, de son nom ou du nom de son entreprise.

WOPR n’affiche que les correspondances utiles.

Lorsqu’une fiche est choisie, ses coordonnées sont automatiquement reprises.

WOPR conserve également ses mécanismes historiques de rapprochement par e-mail ou téléphone lorsqu’aucune sélection explicite n’a été effectuée.

### 6.2 Adresse et ville

Le code postal peut proposer automatiquement la ville à partir d’une base locale.

Si un code postal correspond à plusieurs communes, WOPR affiche les choix possibles. Il ne choisit pas arbitrairement une commune.

La saisie manuelle reste toujours possible.

Cette assistance est également utilisée dans les écrans de modification et dans la Facture simple.

### 6.3 Informations enregistrables

Une réparation peut notamment contenir :

- client et coordonnées ;
- entreprise ;
- date de réception ;
- appareil ;
- panne déclarée ;
- accessoires ;
- système ;
- diagnostic ;
- informations techniques ;
- état d’avancement ;
- mot de passe système protégé ;
- montant de prestation ;
- montant de marchandise ;
- modalités de remise ;
- remarques ;
- facturation ;
- encaissement ;
- signature ;
- documents associés.

### 6.4 Statuts

Les statuts permettent d’organiser le travail.

Exemples :

- Reçu
- Diagnostic
- En attente accord
- En attente pièce
- En réparation
- Terminé
- Restitué

Ils sont utilisés par le tableau de bord, le Suivi et certains filtres.

---

## 7. Suivi des réparations

Le **Suivi** est la vue centrale des réparations.

Les dossiers sont regroupés par année et par mois.

Il est possible de :

- rechercher un client ou un dossier ;
- filtrer les matériels à restituer ;
- ouvrir le dossier ;
- modifier une ligne ;
- accéder à la facture ;
- facturer ;
- consulter l’encaissement ;
- ouvrir le dossier documentaire ;
- exporter en CSV.

### 7.1 Rôle comptable

Le Suivi constitue la référence comptable interne utilisée pour le CA.

Les PDF ne sont pas analysés pour récupérer les montants.

### 7.2 Affichage des tableaux

Les tableaux larges restent utilisables sur des écrans 2K/4K grâce au défilement horizontal.

La légende suit la largeur réelle du tableau et ne déborde plus sur l’espace vide du conteneur.

### 7.3 Documents

Les PDF générés sont affichés directement dans le navigateur lorsque cela est possible.

Le bouton **Dossier** ouvre le répertoire dans lequel le document est archivé.

---

## 8. Facturation

### 8.1 Facture liée à un dossier

Une réparation peut être facturée à partir de sa fiche.

La facture peut contenir plusieurs lignes de prestation et de marchandise.

Une facture existante peut être modifiée sans recréer le dossier.

La date de facture peut être corrigée indépendamment du numéro de facture.

Les remarques de réparation restent rattachées au Suivi et ne sont pas supprimées par l’éditeur de facture.

### 8.2 Liste Factures

La page **Factures** permet :

- la recherche ;
- l’ouverture du PDF ;
- le choix de la langue ;
- l’impression ;
- la modification ;
- l’envoi ;
- l’ouverture du dossier d’archive.

### 8.3 PDF multilingues

Les documents peuvent être générés dans plusieurs langues selon le type de document :

- français ;
- anglais ;
- ukrainien ;
- espagnol ;
- allemand ;
- italien.

L’interface de WOPR reste en français.

### 8.4 Affichage inline

Les PDF sont ouverts dans le lecteur du navigateur au lieu d’être téléchargés automatiquement.

### 8.5 Facture simple

La Facture simple permet de créer une facture sans dossier de réparation complet.

Elle accepte les lignes de prestation et de marchandise et bénéficie également de l’aide code postal / ville.

### 8.6 Classement

Les factures sont classées dans :

`private/documents/Factures/YYYY/MM - Mois/`

---

## 9. Devis

La section **Devis** permet :

- de créer un devis ;
- d’ajouter des prestations et marchandises ;
- de modifier un devis ;
- de générer le PDF ;
- d’ouvrir les documents originaux associés ;
- d’envoyer le devis ;
- d’ouvrir son dossier ;
- de supprimer le devis.

Les fichiers supplémentaires liés à un même devis restent associés au devis concerné et ne sont pas considérés à tort comme des doublons.

### 9.1 Devis historiques

L’historique client peut retrouver certains anciens devis créés avant la liaison systématique par identifiant client.

Le rattachement automatique n’est effectué que lorsqu’il est non ambigu.

---

## 10. Clients et contacts

La page **Clients** centralise les fiches et coordonnées.

Fonctions disponibles :

- recherche ;
- historique ;
- SMS / message ;
- modification ;
- fusion ;
- archivage ;
- restauration ;
- suppression volontaire des fiches de test ;
- import Google CSV ;
- import Proton VCF ;
- export Google CSV ;
- export Proton CSV ;
- export VCard ;
- synchronisation Google Contacts.

### 10.1 Actions compactes

Les boutons d’action sont organisés de façon compacte afin de réduire la largeur du tableau sans perdre les fonctions.

### 10.2 Archivage et suppression

Un vrai client ayant un historique doit normalement être **archivé**.

La suppression définitive est réservée aux fiches de test ou créées par erreur et demande une confirmation explicite.

### 10.3 Historique

La fiche d’historique permet notamment de retrouver :

- dossiers ;
- factures ;
- devis ;
- dernière intervention ;
- dernier dossier ;
- dernière facture ;
- dernier devis ;
- éléments à surveiller.

### 10.4 Google Contacts

La synchronisation Google est volontairement prudente.

Les opérations **WOPR vers Google** et **Google vers WOPR** sont distinctes.

La suppression Google est explicite.

La synchronisation de masse évite de renvoyer inutilement tous les contacts déjà synchronisés.

Une progression et un résumé final indiquent ce qui a été effectué.

Après modification d’un client, la recherche et le contexte courant sont conservés.

---

## 11. Recherche globale

La recherche globale est accessible directement depuis la barre supérieure.

Elle accepte plusieurs mots et ignore les différences :

- d’accents ;
- de casse ;
- de ponctuation.

Elle peut rechercher dans différentes informations :

- noms et entreprises ;
- téléphones ;
- courriels ;
- numéros de dossier ;
- appareils ;
- problèmes ;
- diagnostics ;
- systèmes ;
- statuts ;
- accessoires ;
- factures ;
- devis ;
- lignes de devis ;
- opérations Achats / Ventes.

---

## 12. Achats / Ventes

La section **Achats / Ventes** sert au suivi des opérations et justificatifs.

Elle permet :

- d’ajouter une opération ;
- de rechercher ;
- de modifier directement une ligne ;
- de supprimer ;
- de joindre un justificatif ;
- d’ouvrir le justificatif d’un achat ;
- d’ouvrir la facture client d’une vente ;
- d’ouvrir le dossier correspondant ;
- de contrôler les liens cassés ;
- de consulter les archives annuelles.

### 12.1 Documents fournisseurs

Organisation officielle :

`private/documents/Fournisseurs/YYYY/MM - Mois/`

WOPR accepte différents formats de justificatifs selon les cas : PDF, XML ou image.

### 12.2 Recherche du bon justificatif

Pour éviter d’ouvrir une mauvaise facture, WOPR privilégie les critères les plus fiables.

Ordre général :

1. numéro de facture ;
2. nom original du document ;
3. ancien chemin si le nom reste cohérent ;
4. fournisseur + date si la correspondance est unique ;
5. recherche globale contrôlée.

Les anciennes conventions de nommage restent prises en compte lorsque cela est nécessaire.

### 12.3 Règle comptable

Les justificatifs n’ajoutent pas de CA.

Le chiffre d’affaires officiel reste issu du Suivi.

---

## 13. Abby

L’intégration **Abby** est optionnelle.

Selon la configuration et les possibilités du compte, WOPR peut notamment :

- mémoriser la configuration ;
- tester la connexion ;
- synchroniser des clients ;
- consulter les erreurs ;
- importer certaines factures fournisseurs électroniques ;
- détecter les doublons.

Les clés et paramètres Abby restent dans la partie privée.

---

## 14. Antivirus

La page **Antivirus** sert de registre pour les licences et renouvellements.

Pour chaque ligne, WOPR peut mémoriser :

- le client ;
- la date de mise en place ;
- le produit ;
- la date d’expiration ;
- le numéro de facture ;
- une information de licence ou remarque.

Des compteurs indiquent :

- les licences valides ;
- les licences à renouveler dans les 30 jours ;
- les licences expirées.

L’édition se fait directement dans la ligne :

- **Éditer** active les champs ;
- **Valider** enregistre ;
- **Annuler** abandonne les changements ;
- **Supprimer** efface la ligne après confirmation.

Dans le thème 8-BIT, ces boutons suivent la même logique de couleurs et le même skin que les autres actions.

---

## 15. CA / Déclarations

La page **CA / Déclarations** présente les valeurs nécessaires au suivi administratif.

Les montants automatiques proviennent du Suivi et des champs comptables associés.

Principe à retenir :

**un seul référentiel de CA = le Suivi**

Une correction d’un PDF ne doit donc pas être utilisée pour corriger le CA.

---

## 16. Communication client

WOPR peut préparer différents messages :

- suivi de réparation ;
- facture ;
- devis ;
- message libre.

Le salut utilisé par défaut est neutre :

`Bonjour,`

Selon la configuration, l’envoi peut utiliser :

- SMTP Proton pour l’e-mail ;
- KDE Connect pour le SMS ;
- un texte préparé à copier dans un autre service.

WOPR reste utilisable même si ces intégrations ne sont pas configurées.

---

## 17. Sécurité locale

La page **Sécurité** regroupe plusieurs fonctions sensibles.

### 17.1 PIN administrateur

Le PIN protège l’accès atelier.

Il est stocké sous forme de hash.

### 17.2 Clé maître

Les secrets locaux peuvent être chiffrés.

La clé maître doit être conservée avec soin. Une clé maître perdue ne peut pas être reconstruite à partir de la documentation.

### 17.3 Mots de passe appareil

Lorsqu’un mot de passe système est enregistré dans un dossier, il n’est pas affiché directement dans le HTML.

Sa consultation utilise une action protégée.

### 17.4 SMTP

Les réglages SMTP et jetons restent locaux.

### 17.5 Logo facture

Le logo choisi par l’utilisateur est enregistré dans `private/assets/`.

Il n’est pas inclus dans le coeur public du projet.

### 17.6 Diagnostic de portabilité

Le diagnostic vérifie notamment :

- le coeur public ;
- la structure privée ;
- les droits d’écriture ;
- la présence du lanceur source ;
- le binaire Linux ;
- le binaire Windows.

---

## 18. Sauvegardes

WOPR conserve un nombre limité de sauvegardes récentes afin d’éviter une croissance infinie du dossier.

La politique actuelle prévoit notamment :

- jusqu’à 30 sauvegardes ;
- une sauvegarde de démarrage au maximum une fois par jour ;
- une sauvegarde d’arrêt uniquement si la base a changé ;
- des sauvegardes forcées avant certaines opérations sensibles.

Une sauvegarde manuelle reste disponible.

---

## 19. Organisation des documents

Les documents sont stockés dans la partie privée.

Organisation principale :

```text
private/
└── documents/
    ├── Devis/
    ├── Factures/
    │   └── YYYY/
    │       └── MM - Mois/
    ├── Fournisseurs/
    │   └── YYYY/
    │       └── MM - Mois/
    └── Suivi de réparation/
        └── YYYY/
            └── MM - Mois/
```

Les vues concernées proposent un bouton **Dossier** pour accéder directement au répertoire correspondant.

---

## 20. Organisation générale des données

Structure simplifiée d’une installation :

```text
WOPR/
├── WOPR
├── WOPR.exe
├── README.md
├── LICENSE
├── public/
│   ├── app.py
│   ├── requirements.txt
│   ├── launcher/
│   │   └── wopr_launcher.py
│   ├── templates/
│   └── static/
├── docs/
└── private/              # NE PAS PUBLIER
    ├── data/
    ├── documents/
    ├── signatures/
    ├── assets/
    └── seeds/
```

La partie `public/` peut être diffusée.

La partie `private/` appartient à l’installation et peut contenir des informations confidentielles.

---

## 21. Licence GNU GPLv3

WOPR est publié sous licence **GNU General Public License version 3**.

Le texte juridique complet se trouve dans le fichier `LICENSE` fourni avec le projet.

### 21.1 Ce que permet la GPLv3

La GPLv3 autorise notamment à :

- utiliser WOPR ;
- étudier son code source ;
- modifier le logiciel ;
- redistribuer des copies ;
- redistribuer des versions modifiées.

### 21.2 Obligations principales lors d’une redistribution

Lorsqu’une redistribution entre dans le cadre de la GPLv3, il faut notamment conserver les libertés prévues par la licence et fournir les éléments requis par celle-ci, notamment le code source correspondant lorsque cela s’applique.

Les mentions de copyright et la licence doivent être conservées selon les conditions de la GPLv3.

### 21.3 Gratuité de WOPR

La GPLv3 n’interdit pas en elle-même de demander de l’argent pour distribuer un logiciel.

**Foul-Fix choisit cependant de distribuer WOPR gratuitement.**

Il n’existe pas de version Premium et aucun don n’est requis pour accéder à une fonction.

Pour les détails juridiques, le fichier `LICENSE` fait foi.

---

## 22. Soutien PayPal

WOPR est gratuit.

Si l’utilisateur souhaite soutenir volontairement le projet :

**PayPal : https://paypal.me/foul**

![QR code PayPal](images/paypal-qr.png)

Le soutien est facultatif.

Aucune fonctionnalité n’est bloquée sans don.

---

## 23. Publication sur GitHub

Avant une publication, vérifier impérativement qu’aucune donnée privée n’est incluse.

### À publier

- code public WOPR ;
- templates génériques ;
- ressources publiques ;
- source du lanceur ;
- dépendances ;
- documentation ;
- licence ;
- fichiers nécessaires à la distribution.

### À ne jamais publier

- `private/` ;
- bases SQLite réelles ;
- sauvegardes ;
- clés ;
- jetons ;
- secrets SMTP ;
- identifiants OAuth ;
- signatures ;
- factures et devis clients réels ;
- exports clients ;
- captures non anonymisées.

### Script de publication

Le script `Update-WOPR.sh` effectue notamment :

- les contrôles de sécurité ;
- la vérification de la version ;
- le commit et le push GitHub ;
- la synchronisation du dossier `docs/` vers le site ;
- la préparation des notes depuis `docs/CHANGELOG-DOC.md` ;
- la création ou la vérification de la release GitHub ;
- la création du ZIP public.

---

## 24. Dépannage rapide

### WOPR ne démarre pas

Vérifier :

- Python ;
- les dépendances ;
- le lanceur ;
- les messages affichés au démarrage ;
- les fichiers présents dans l’installation.

### Une intégration Google / Abby / SMTP ne fonctionne pas

Ces fonctions nécessitent leur propre configuration.

Commencer par vérifier les paramètres locaux et le test de connexion associé.

### Un justificatif ne s’ouvre plus

Utiliser le contrôle des justificatifs d’Achats / Ventes et vérifier que le fichier n’a pas été déplacé ou renommé en dehors de WOPR.

### Le CA semble incohérent

Contrôler le Suivi, les montants et les dates d’encaissement.

Ne pas essayer de corriger le CA en modifiant uniquement un PDF.

### Perte de clé maître

Conserver une sauvegarde sécurisée de cette clé en dehors du dépôt public.

---

## 25. Nouveautés principales de la release 2.3.285

Cette release consolide une longue série d’améliorations.

Parmi les évolutions visibles :

- interface allégée et uniformisée ;
- Clients plus compacts ;
- Factures, Devis et Achats / Ventes harmonisés ;
- palette d’actions cohérente ;
- thème 8-BIT finalisé ;
- boutons Facture et Dossier correctement pris en charge ;
- actions Antivirus harmonisées ;
- tableaux et badges 8-BIT ;
- responsive 2K/4K ;
- affichage inline des PDF ;
- classement automatique des documents ;
- résolution plus robuste des factures fournisseurs ;
- récupération plus sûre des factures clients historiques ;
- sauvegardes intelligentes ;
- synchronisation Google Contacts plus lisible et moins destructive ;
- aide code postal / ville étendue.

---

## 26. Crédit

**Développé par Foul-Fix, avec l’aide de ChatGPT (OpenAI) pour l’assistance au développement, à la documentation et aux tests.**

WOPR est développé comme un outil métier de terrain, avec une priorité donnée à la simplicité d’utilisation, à la portabilité, à la conservation locale des données sensibles et à la réduction des doubles saisies.
