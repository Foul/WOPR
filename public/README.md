# Foul-Fix v2.3.92

- Bouton Atelier séparé de la navigation principale.
- Positionné entre le badge de version et le bouton Nouvelle réparation.
- Espacement dédié pour bien le distinguer visuellement.
- Données existantes non incluses dans cette mise à jour.

# Foul-Fix — UPDATE v2.3.82

## Correctif encaissement / restitution inter-mois
- Une facture encore rouge qui passe en **Restitué** est automatiquement encaissée à la date du jour.
- Un bouton **Encaisser aujourd’hui** apparaît pour une ligne Restituée encore en attente de paiement.
- Les règlements encaissés sur un mois différent du suivi apparaissent aussi visuellement dans le mois d’encaissement (ligne d’affichage uniquement, sans doubler le CA).
- Le total mensuel reste calculé depuis les champs comptables réels.
- Version API : 2.3.82.

# Foul-Fix API v2.3.80

Mise à jour sans données utilisateur.

## Nouveautés
- Chiffrement Fernet des mots de passe appareils dans `foulfix.db`.
- Migration automatique des anciens mots de passe stockés en clair.
- Les mots de passe ne sont plus injectés dans le HTML : révélation uniquement au clic sur l'œil, via requête protégée par session + CSRF.
- Lors d'une modification, laisser le champ mot de passe vide conserve le mot de passe déjà enregistré.
- La sauvegarde automatique reste limitée à une sauvegarde par jour, avec conservation des 30 derniers jours.
- La clé maître reste hors du projet : `~/.config/Foul-Fix/master.key` sous Linux.

## Important
Ne supprime pas `master.key`. Sans elle, les secrets chiffrés (Abby, SMTP, mots de passe appareils) ne sont plus déchiffrables.


## V2.3.81
- Correction encaissement : passage d'une attente (rouge) à réglé sans date => date du jour.
- Sur une fiche facturée non réglée, possibilité de cocher “Paiement reçu aujourd’hui” lors de la restitution.
- Le CA est automatiquement affecté au mois réel d'encaissement; si différent du mois du suivi, la ligne devient jaune.


# Foul-Fix — UPDATE v2.3.83

## Gestion atelier / restitutions
- Bouton **À restituer (X)** dans le Suivi pour n'afficher que les matériels terminés encore présents.
- Bouton **Restituer** directement dans la ligne, sans ouvrir la fiche.
- Si la facture est encore en attente, **Restituer + encaisser** demande le mode de règlement et affecte automatiquement le CA au vrai mois d'encaissement.
- Enregistrement de la date et de l'heure réelle de restitution (`returned_at`).
- Historique des changements de statut dans chaque dossier.
- Alerte visuelle à partir de 7 jours d'attente de restitution, renforcée à partir de 15 jours.
- Modifier une facture d'un dossier déjà Restitué ne le repasse plus en Terminé.
- Version API : 2.3.83.

### v2.3.84 — Suivi atelier fiabilisé
- Le compteur « À restituer » ignore désormais les anciennes lignes comptables « Paiement du… » et correspond aux dossiers réellement affichés.
- Ajout d'une recherche client directement dans le Suivi (nom, prénom, téléphone), compatible avec le filtre « À restituer » et les onglets d'année.
- Restitution d'un dossier non réglé simplifiée : un seul bouton « Restituer » ouvre les modes de règlement sous forme de boutons ESP/CB/VIR/PAY/BTC/CHQ.


## v2.3.85 — Paiement = restitution
- Suppression du bouton de restitution rapide dans le Suivi.
- Le fonctionnement revient à l'édition via **Modifier**, comme avant.
- Dès qu'un règlement est enregistré, le dossier passe automatiquement en **Restitué** et la date/heure de restitution est mémorisée.
- La même logique est appliquée depuis l'édition du Suivi, la fiche réparation et la facturation.


## v2.3.86 — restitution à la date uniquement
- La restitution enregistre uniquement la date (JJ/MM/AAAA), sans heure.
- Les anciennes restitutions horodatées restent compatibles mais l’heure n’est plus affichée.
- La logique paiement = restitution reste inchangée.

## v2.3.87 — Tableau de bord atelier
- Nouvelle page **Atelier** accessible depuis la barre du haut.
- Vue synthétique : En cours, Attente pièce, À restituer, Impayés, CA du mois, réparations entrées ce mois.
- Bloc **À surveiller** pour les matériels terminés depuis 7 jours ou plus.
- Bloc des règlements en attente et accès direct aux dossiers.
- Le Suivi historique reste inchangé.


## v2.3.89 — Date du jour dans Achats / Ventes
- Le formulaire « Ajouter une opération » propose désormais automatiquement la date du jour.
- La date reste modifiable avant validation.


## v2.3.89
- Tableau Atelier : calcul des impayés aligné sur la page Factures, une facture = une ligne.
- Atelier déplacé à gauche et séparé visuellement dans la navigation.


## V2.3.92 — Factures fournisseurs liées aux achats
- Une facture PDF/XML/JPG/PNG peut être jointe lors de l'ajout d'un achat.
- Une facture peut aussi être jointe après coup depuis la ligne Achats/Ventes.
- Les pièces sont rangées dans `Factures/AAAA/MM - Mois/Fournisseurs` sans créer de sous-dossiers supplémentaires.
- Nommage des nouvelles pièces : `FOURNISSEUR_NumeroFacture.ext` (ex. `SLE-FRANCE_20260903-0006.pdf`).
- Si le même fichier existe déjà, Foul-Fix le réutilise au lieu de créer un doublon.
- Le bouton 📄 ouvre directement la pièce liée depuis Achats/Ventes.
- Les imports XML Abby enregistrent eux aussi le lien vers leur pièce.


## V2.3.92
- Atelier devient la page d’accueil (`/`).
- Suivi passe sur `/suivi`.
- Les justificatifs fournisseurs sont visibles dans une colonne dédiée `Justificatif` (📄 Ouvrir / 📎 Joindre).
- Compteur des factures fournisseurs liées et des achats sans justificatif.


## V2.3.93 — Fournisseurs + rattachement automatique 2025–2026
- Dossier unique : `Factures/AAAA/MM - Mois/Fournisseurs` (pluriel).
- Les factures historiques déjà classées ne sont ni déplacées, ni copiées, ni renommées.
- Bouton `Rattacher automatiquement 2025–2026` dans Achats/Ventes.
- Rapprochement prudent par numéro de facture, fournisseur et date ; seuls les matchs sûrs sont liés.
- Les cas ambigus restent volontairement non liés.
- Nouvelles factures jointes : nom maison `FOURNISSEUR_NumeroFacture.ext`.
- Compatibilité de lecture avec les anciens liens 2.3.91/2.3.92 au singulier si le fichier a été replacé dans `Fournisseurs`.


## v2.3.94 — anti-bazar factures fournisseurs
- Les bons de commande ne sont plus traités comme des numéros de facture fournisseur.
- Les anciens numéros internes/date-heure Amazon/eBay issus de l'import ODS ne servent plus au nommage ni au rapprochement automatique.
- Exemple exclu : `60820261300` quand il s'agit d'une référence historique Amazon et non d'une facture fournisseur.
- Foul-Fix ne crée plus de nom du type `Amazon_BON DE COMMANDE ...pdf` ou `Amazon_60820261300.pdf` à partir de ces références.

## v2.3.95 — anti-doublons strict dans Fournisseurs
- Lorsqu'une facture est déjà présente dans le dossier `Fournisseurs`, l'ajout depuis Achats/Ventes compare le contenu exact du fichier avant toute copie.
- Si le même PDF/XML/image existe déjà, Foul-Fix le rattache directement à l'achat et ne crée aucun second fichier, même si son nom diffère.
- Nettoyage automatique unique des doublons strictement identiques éventuellement créés par les versions 2.3.91 à 2.3.94 : les liens en base sont repointés vers le fichier le plus ancien avant suppression de la copie.
- Aucun fichier différent n'est fusionné ou supprimé.


## V2.3.96 — Réparation des liens de justificatifs
- Corrige les anciens liens de factures fournisseurs devenus invalides après dédoublonnage.
- Recherche en priorité le nom original réellement choisi par l'utilisateur dans le dossier `Fournisseurs` du mois.
- Répare ensuite le chemin enregistré en base, sans créer, copier, renommer ni supprimer de fichier.
- Le fallback automatique reste limité aux rapprochements sûrs.


## v2.3.99 — Recherche Achats / Ventes, sans rattachement automatique
- Suppression du bouton « Rattacher automatiquement 2025–2026 ».
- Suppression de la route de rattachement automatique : aucune facture n'est liée en masse.
- Nouveau champ/bouton « 🔎 Rechercher » dans Achats / Ventes.
- Recherche dans fournisseur/client, date, article, montant, mode de paiement, numéro de facture, remarques et nom du justificatif.
- Bouton « ✕ Effacer » pour revenir immédiatement à la liste complète.

## v2.3.97 — Fournisseurs : zéro doublon automatique
- Le rattachement manuel cherche d'abord une facture déjà classée dans le dossier Fournisseurs du mois, même si le PDF n'est pas strictement identique octet pour octet.
- Correspondance forte par numéro de facture ou nom d'origine normalisé : le fichier existant est lié, aucune copie n'est créée.
- Si plusieurs fichiers semblent correspondre, Foul-Fix refuse de copier et demande une vérification au lieu de choisir au hasard.
- Si le nom de destination existe déjà avec un contenu différent, Foul-Fix refuse désormais de créer un suffixe « - 2 ».
- Aucun nettoyage destructif approximatif : seuls les doublons strictement identiques restent concernés par le nettoyage existant.


## v2.3.99
- Recherche globale en lecture seule : clients, réparations, achats/ventes, devis.
- Historique client complet avec dossiers et devis.
- Contrôle des justificatifs fournisseurs strictement en lecture seule.


## v2.3.100 — Justificatif des ventes = facture client

- Dans Achats / Ventes, la colonne `Justificatif` garde la facture fournisseur pour les `Achat`.
- Pour les lignes `Vente`, la colonne affiche désormais `📄 Ouvrir` si le numéro de facture correspond à une facture Foul-Fix.
- Le bouton ouvre directement la facture client existante.
- Aucun PDF de vente n'est copié, renommé ou dupliqué dans `Fournisseurs`.


## v2.3.101 — Ouverture de la bonne facture client
- Corrige le bouton `📄 Ouvrir` des lignes Vente dans Achats / Ventes lorsqu'un même numéro de facture existe dans plusieurs dossiers historiques.
- Le client de la ligne (`party`) est désormais utilisé en priorité pour choisir le bon dossier/fichier PDF.
- Exemple : `Mme Jacquement` + `180820261600` ouvre bien `Jacquement_180820261600.pdf`.
- Les différentes lignes d'une même facture client ouvrent toutes le même PDF de facture complète.


## v2.3.102 — ouverture déterministe de la facture client
- Achats/Ventes n'ouvre plus une facture via un dossier de réparation ambigu.
- La ligne Vente cherche directement le PDF réellement classé dans `Factures`.
- Le nom canonique sans civilité est prioritaire : `Jacquement_180820261600.pdf` passe avant `Mme_Jacquement_180820261600.pdf`.
- Aucun PDF n'est créé, renommé, déplacé ou supprimé.


## v2.3.103 — CA verrouillé sur le Suivi
- Source de vérité unique pour les chiffres de vente et le CA : `repairs` / Suivi (`accounting_service_amount` + `accounting_goods_amount`).
- Achats / Ventes affiche désormais les totaux de ventes mensuels et annuels depuis le Suivi, comme CA / Déclarations et Atelier.
- Les PDF clients et fournisseurs sont strictement des justificatifs : aucun montant n'est extrait d'un PDF et aucun PDF ne peut modifier le CA.
- Le montant `Règlement TTC` d'une ligne Vente reste un détail de la ligne Achats/Ventes et n'est pas utilisé pour le CA officiel.
- La recherche Achats/Ventes ne modifie plus les totaux officiels affichés.

## v2.3.105 — Clients : action Resync supprimée
- Suppression du bouton individuel **Resync.** dans la colonne Actions de la page Clients.
- Conservation de **Synchroniser tous les clients maintenant** comme action de synchronisation Google principale.
- La synchronisation automatique lors des créations/modifications de clients reste inchangée.


## v2.3.105 — Refonte Historique client
- Mise en page structurée avec résumé client et cartes statistiques.
- Bloc À surveiller (dossiers actifs, à restituer, impayés).
- Tableaux Réparations/Factures et Devis réorganisés.
- Montants issus uniquement des données Suivi, jamais des PDF.

## v2.3.106 — Clients entreprise sans nom/prénom
- Une fiche Client peut désormais être une entreprise seule.
- Si Prénom et Nom sont vides, le champ Entreprise / Société devient le nom principal de la fiche.
- La validation accepte donc : personne (nom/prénom) OU entreprise.
- La synchronisation Google/Abby conserve le champ entreprise.



## v2.3.107 — Entreprises : nom visuel corrigé
- Une entreprise sans prénom/nom reste affichée uniquement dans la colonne Entreprise/Société.
- Le champ interne `name` peut conserver la raison sociale pour compatibilité, mais il n'est plus réinjecté visuellement dans la colonne Nom.
- Historique, recherche globale et facture simple évitent aussi le doublon raison sociale / nom.

## v2.3.108 — PDF multilingues
- L'interface, le Suivi et les données Foul-Fix restent intégralement en français.
- Les PDF Facture et Prise en charge peuvent être générés en FR / EN / UA / ES / DE / IT.
- Le design Foul-Fix, le logo, les montants et les données restent inchangés ; seule la langue du rendu PDF change.
- Les libellés fixes, mentions, titres et formulations atelier courantes sont traduits au rendu.
- Les textes techniques inconnus du glossaire restent tels qu'ils ont été saisis afin de ne jamais inventer une traduction technique.
- Le nom de fichier contient le suffixe de langue : `_FR`, `_EN`, `_UA`, `_ES`, `_DE`, `_IT`.
- L'envoi de facture par e-mail permet aussi de choisir la langue de la pièce jointe, sans traduire l'interface ni le message.

## v2.3.109 — Traductions PDF : prestations complétées
- Complète le dictionnaire multilingue des libellés de réparation signalés lors du test anglais.
- Ajoute les équivalents EN / UA / ES / DE / IT pour le passage hors mode S de Windows 11, la suppression de spywares, la suppression de logiciels inutiles + installation des indispensables et Windows Update.
- La traduction reste strictement limitée au rendu PDF : aucune donnée du Suivi n'est modifiée.


## v2.3.110 — Favicon Foul-Fix
- Ajout du favicon fourni par Foul-Fix sur toutes les pages.
- Ajout des formats PNG, ICO et Apple Touch Icon.
- Versionnage des liens favicon pour éviter le cache navigateur.


## v2.3.111 — Pied de facture multilingue
- Le pied légal des factures PDF est désormais traduit en EN / UA / ES / DE / IT.
- SIRET et code APE gardent leurs identifiants officiels, avec libellés traduits.
- IBAN, site et e-mail restent inchangés.
- La version française reste la référence et aucune donnée Suivi n’est modifiée.


## v2.3.112 — Suivi allégé : historique retiré
- Suppression de l’affichage « Historique du dossier » dans la fiche Suivi.
- La fiche revient à l’essentiel : données du dossier, actions, PDF et facturation.
- Les anciennes données d’historique restent en base pour compatibilité et ne sont pas supprimées.


## v2.3.113 — Thème 8-bits optionnel
- Ajout d’un bouton 🕹️ dans la barre supérieure pour basculer entre le thème normal d’origine et un thème 8-bits/pixel.
- Le choix est mémorisé localement dans le navigateur et restauré automatiquement au prochain lancement.
- Le thème 8-bits modifie surtout la navigation et les boutons, avec reliefs durs, coins carrés et palette rétro, sans toucher aux données ni au fonctionnement de Foul-Fix.
- Le thème normal reste strictement disponible à tout moment.


## v2.3.114 — Correctif écran blanc thème 8-bits
- Correction du script de sélection du thème dans `base.html` : balise `</script>` manquante.
- Restaure immédiatement le rendu normal de toutes les pages.
- Conserve le choix Normal / 8-BIT et sa mémorisation locale.


## v2.3.115 — Thème 8-BIT : boutons rétro arcade
- Refonte visuelle du thème 8-BIT pour coller au concept validé : gros boutons en relief, coins crénelés, cadres internes, ombres dures et icônes en cases façon sprite.
- `Nouvelle réparation` devient le bouton bleu lumineux principal.
- La page active utilise un bouton clair/blanc comme dans la maquette.
- Le thème Normal reste strictement disponible et inchangé.


## v2.3.116 — Thème 8-BIT fidèle au concept
- Navigation 8-BIT agrandie et redessinée pour reproduire la proposition visuelle validée.
- Cartouches arcade épais, relief pixel, icônes sprite, bouton actif clair et Nouvelle réparation bleu électrique.
- Thème Normal conservé tel quel.


## v2.3.117 — Thème 8-BIT navigation only
- conserve le look 8-BIT / arcade sur la barre du haut, les boutons de navigation et la bascule de thème ;
- remet le contenu des pages (tableaux, formulaires, cartes, textes) en style normal pour garder une excellente lisibilité ;
- supprime le fond sombre / grille et la typographie monospace dans le contenu ;
- restaure les boutons standards à l'intérieur des pages.


## v2.3.118 — 8-BIT plus fidèle à la maquette
- thème 8-BIT conservé en navigation only, avec boutons retravaillés pour ressembler davantage à la première maquette validée ;
- logo Foul-Fix spécifique au thème 8-BIT, inspiré de la proposition validée ;
- topbar et cartouches nav plus proches du rendu arcade/pixel attendu.


## v2.3.119 — Paiements mixtes
- ajout du mode MIXTE pour une facture réglée avec plusieurs moyens de paiement ;
- ventilation possible entre espèces, CB, virement, PayPal, Bitcoin et chèque ;
- contrôle strict : la somme ventilée doit correspondre exactement au total de la facture ;
- le CA reste comptabilisé une seule fois sur le montant total encaissé ;
- le détail est conservé et affiché, par exemple `30,00 € ESP + 39,00 € CB`.


## v2.3.120 — Paiement mixte corrigé
- la ventilation MIXTE est disponible directement dans Modifier depuis le Suivi ;
- les montants saisis dans Modifier facture sont relus et préremplis lors de la réouverture ;
- même préremplissage dans la fiche complète ;
- la ventilation est validée contre le total exact avant enregistrement ;
- le CA reste compté une seule fois sur le total encaissé.

## v2.3.121 — Séparation Suivi / Facturation
- le bouton « Modifier » du Suivi ouvre directement la fiche de réparation ;
- la fiche de Suivi ne contient plus les champs de facturation, règlement ou comptabilité ;
- « Modifier facture » reste dédié à la facturation ;
- modifier le Suivi ne touche plus aux montants, au mode de paiement, à l'encaissement ni au CA.


## v2.3.122 — 8-BIT fidèle à la maquette + couleurs Suivi
- rétablit les couleurs métier du Suivi en thème 8-BIT (rouge attente de règlement, jaune de repère, badges, total/mode) ;
- retravaille fortement les boutons de navigation 8-BIT pour se rapprocher de la première proposition validée ;
- conserve la navigation rétro tout en gardant les pages intérieures lisibles.


## v2.3.123 — Atelier intégré à la barre 8-BIT
- supprime le bouton Atelier flottant au-dessus ;
- replace Atelier directement dans la barre de navigation, sur la même ligne que les autres boutons ;
- ajoute un séparateur visuel après Atelier pour se rapprocher de la première maquette ;
- agrandit et retouche encore les boutons 8-BIT ;
- conserve les couleurs métier du Suivi en thème 8-BIT.


## v2.3.124 — Boutons 8-BIT calés sur la maquette
- les bordures des boutons 8-BIT utilisent directement des éléments graphiques extraits de la première maquette validée ;
- bouton standard, bouton bleu « Nouvelle réparation », bouton actif blanc et badge API ont chacun leur habillage issu de la maquette ;
- suppression des gros cartouches d'icônes façon interface moderne ;
- couleurs métier du Suivi conservées en thème 8-BIT.


## v2.3.125 — Fix Atelier actif 8-BIT
- corrige uniquement le bouton Atelier quand la page Atelier est active ;
- supprime les héritages d’anciens styles Atelier ;
- applique exactement le même habillage actif blanc que les autres boutons 8-BIT.


## v2.3.127 — Boutons 8-BIT sans chevauchement
- corrige le chevauchement entre le rendu normal et le rendu 8-BIT sur les boutons ;
- remplace les sprites contaminés par des variantes nettoyées, ne contenant plus le texte/icône du centre ;
- conserve le style 8-BIT de la maquette ;
- Atelier reste sombre sur la page Atelier, sans double bouton visuel.


## v2.3.128 — override final boutons 8-BIT
- écrase les anciens styles résiduels plus spécifiques sur tous les boutons de navigation ;
- utilise uniquement les sprites nettoyés ;
- supprime les pseudo-éléments parasites ;
- corrige le chevauchement persistant sur Atelier et le reste de la barre.


## v2.3.129 — KPI Impayés + libellé TTC
- le clic sur « Impayés » dans Atelier ouvre désormais la page Factures filtrée sur les factures réellement impayées ;
- un bandeau permet de voir clairement que le filtre Impayés est actif et de revenir à toutes les factures ;
- dans Achats / Ventes, l'en-tête affiche simplement « Règlement TTC » : suppression du symbole ⓘ.


## v2.3.130 — boutons 8-BIT en skin plein
- remplace le système border-image qui donnait l’impression d’un bouton normal posé sur un cadre 8-bit ;
- les boutons 8-bit utilisent désormais directement un sprite plein comme background ;
- même correction pour Atelier, les autres boutons, API et la bascule de thème.


## v2.3.131 — Skins 8-BIT reconstruits proprement
- les anciens sprites issus de captures ne sont plus utilisés pour les boutons ;
- nouveaux skins pixel-art reconstruits sans texte, sans icône et sans morceau de bouton voisin ;
- corrige le faux « bouton normal par-dessus » visible sur Recherche et les autres boutons actifs ;
- Atelier reste sombre même actif.


## v2.3.132 — Sélection navigation Facture simple
- sur la page « Facture simple », seul le bouton « Facture simple » est actif/blanc ;
- le bouton « Factures » ne s'active plus en même temps ;
- sur la page « Factures », seul « Factures » reste actif.


## v2.3.133 — CA / Déclarations en-tête corrigé
- « ACTIVITÉS » n'est plus affiché en énorme ;
- la ligne de déclaration affiche maintenant en entier : « Déclaration URSSAF / IMPÔTS / Formulaire 2042 C PRO » ;
- l'en-tête est rééquilibré pour laisser davantage de place au texte central.


## v2.3.134 — Nettoyage complet du thème 8-BIT
- suppression de tous les anciens blocs CSS 8-BIT accumulés depuis les premières tentatives ;
- un seul bloc CSS 8-BIT consolidé reste actif ;
- suppression des anciens sprites découpés / nettoyés devenus inutiles ;
- seuls `pixel_btn_std_v2.png`, `pixel_btn_new_v2.png`, `pixel_btn_active_v2.png` et `pixel_badge_v2.png` sont conservés ;
- aucun changement de logique métier ni de données.


## v2.3.135 — Matériel laissé pour pièces / sans facture
- ajoute un cas explicite « Matériel laissé pour pièces — aucune facture » dans l'écran de facturation ;
- autorise zéro ligne de facture uniquement quand ce cas est coché ;
- clôture le dossier sans facture, sans règlement et sans CA ;
- ajoute le statut final « Laissé pour pièces » ;
- ce statut n'est ni impayé ni à restituer ;
- le Suivi affiche « Sans facture » et le badge « Laissé pour pièces » ;
- propose « Suivi + photos par mail » comme mode de remise/envoi du dossier.


## v2.3.136 — Laissé pour pièces : nettoyage comptable complet
- corrige automatiquement les dossiers déjà marqués « Laissé pour pièces » qui avaient encore 30 € / « En attente » ;
- force 0 € de prestation et 0 € de marchandise ;
- supprime facture, paiement, date d'encaissement et statut comptable rouge ;
- exclut définitivement ces dossiers du CA et des impayés ;
- le Suivi affiche désormais « — » dans Total / Mode au lieu de 30,00 €.


## v2.3.137 — Envoi du suivi + photos sans facture
- pour un dossier « Laissé pour pièces », le bouton d'e-mail devient « Envoyer suivi + photos » ;
- ce nouvel envoi joint uniquement le PDF de suivi, jamais la facture ;
- permet de sélectionner plusieurs photos JPG/JPEG/PNG/WEBP à joindre au mail ;
- le texte proposé rappelle que le matériel est laissé pour pièces en remplacement du forfait diagnostic de 30 € ;
- le bouton d'e-mail d'une vraie facture est désormais libellé clairement « Envoyer la facture ».


## v2.3.138 — Date finale du suivi pour « Laissé pour pièces »
- un dossier « Laissé pour pièces » reçoit désormais toujours une date de clôture ;
- les anciens dossiers déjà dans cet état sans date sont corrigés automatiquement ;
- le PDF de suivi affiche donc bien la date finale même lorsqu'aucune facture n'est créée.


## v2.3.139 — PDF de suivi réellement joint au mail
- génération directe du PDF de suivi avant l'envoi, sans client Flask interne ;
- vérification que les octets générés sont bien un vrai PDF ;
- vérification MIME avant SMTP qu'une pièce jointe application/pdf est réellement présente ;
- l'écran d'envoi précise que le PDF est joint automatiquement.


## v2.3.140 — PDF visible + GIF / vidéos
- l'écran d'envoi affiche désormais une vraie carte de pièce jointe avec le nom et la taille du PDF de suivi préparé ;
- le PDF reste joint automatiquement au message, sans facture ;
- permet d'ajouter photos, GIF et vidéos : JPG, PNG, WEBP, GIF, MP4, MOV, WEBM, M4V, AVI ;
- limite de 20 Mo de médias par e-mail, hors PDF.


## v2.3.141 — Fix erreur 500 sur envoi suivi
- corrige l'erreur 500 provoquée par la lecture du PDF généré via `send_file()` en mode direct passthrough ;
- la carte de pièce jointe peut maintenant afficher réellement le nom et la taille du PDF ;
- le PDF est correctement récupéré puis joint à l'e-mail ;
- conserve l'envoi de photos, GIF et vidéos ajouté en v2.3.140.


## v2.3.142 — Nom PDF suivi identique aux fichiers Suivi
- supprime l'ID interne du dossier dans le nom de la pièce jointe ;
- utilise exactement le même format que le PDF de suivi téléchargé ;
- exemple : `Benoit_Riviere_04092026_FR.pdf`.


## v2.3.143 — Message client
- ajoute un bouton « 💬 Message client » dans la fiche dossier ;
- ajoute une icône 💬 discrète directement dans les actions du Suivi ;
- propose des modèles : automatique selon le statut, diagnostic, demande d'accord, pièce commandée, matériel prêt, laissé pour pièces et message libre ;
- le texte est modifiable avant utilisation ;
- bouton « Copier le message » avec compatibilité presse-papiers KDE Connect ;
- bouton « Ouvrir SMS » via le gestionnaire SMS du système ;
- bouton vers Google Messages Web ;
- aucun SMS n'est envoyé automatiquement par Foul-Fix.


## v2.3.144 — Nettoyage Suivi + retours à la ligne Message client
- corrige les `\n` visibles dans les messages client : ce sont maintenant de vrais retours à la ligne ;
- dans la fiche de suivi, supprime le doublon « Message client » du haut : seul le bouton du bas reste ;
- dans le tableau Suivi, retire « Modifier facture » et « Facture PDF » ;
- ces deux actions restent disponibles dans l'onglet Factures, où elles ont leur place ;
- le bouton « FACTURER » reste visible dans le Suivi uniquement pour un dossier pas encore facturé.


## v2.3.145 — Message client corrigé + SMS depuis Clients
- corrige le dernier `\n` encore visible dans le modèle « Diagnostic en cours » ;
- ajoute un bouton « 💬 SMS » dans la liste Clients quand un numéro est disponible ;
- ajoute aussi « 💬 SMS » dans l'historique client ;
- permet de préparer un message même sans dossier de réparation ouvert ;
- conserve les boutons Copier, Ouvrir SMS et Google Messages.


## v2.3.146 — SMS direct KDE Connect + console discrète
- « Ouvrir SMS » devient un vrai envoi SMS via `kdeconnect-cli --send-sms` ;
- détection automatique des téléphones KDE Connect appairés et joignables ;
- si un seul téléphone est disponible, il est choisi automatiquement ;
- confirmation obligatoire avant l'envoi réel ;
- normalisation automatique des numéros français `06...` / `07...` vers `+33...` ;
- Google Messages et Copier restent disponibles en secours ;
- le raccourci Foul-Fix lance désormais Konsole en `--background-mode` au lieu d'ouvrir une grosse fenêtre Shell ;
- l'installateur du bouton Bureau génère maintenant le raccourci avec le chemin réel de l'installation.


## v2.3.147 — Lancement sans fenêtre Shell
- abandonne `konsole --background-mode`, qui empêchait le raccourci de fonctionner correctement ;
- le raccourci lance maintenant directement `lancer_foulfix_GDRIVE.sh --background` avec `Terminal=false` ;
- Flask est détaché avec `setsid`/`nohup` et écrit dans `data/foulfix-launcher.log` ;
- le navigateur s'ouvre seulement quand le serveur répond ;
- le lancement manuel du script sans `--background` conserve l'ancienne console visible pour le diagnostic.


## v2.3.148 — Script d'arrêt local
- ajoute `arreter_foulfix.sh` directement dans le dossier `foulfix_mvp/` ;
- aucun raccourci Bureau n'est créé ;
- le script lit `data/foulfix.pid`, arrête le processus Foul-Fix, puis supprime le PID.


## v2.3.149 — Bouton Arrêter Foul-Fix
- ajoute `Arreter-Foul-Fix.desktop` directement dans `foulfix_mvp/` ;
- bouton KDE avec l'icône système `process-stop` ;
- un clic lance `arreter_foulfix.sh` sans ouvrir de terminal ;
- aucun nouveau raccourci n'est créé sur le Bureau.


## v2.3.150 — Icône personnalisée pour Arrêter Foul-Fix
- ajoute `stop_foulfix_icon.png` dans `foulfix_mvp/` ;
- `Arreter-Foul-Fix.desktop` utilise maintenant cette icône personnalisée au lieu de `process-stop` ;
- aucun autre comportement n'est modifié.


## v2.3.151 — Icône personnalisée pour Démarrer Foul-Fix
- ajoute `start_foulfix_icon.png` dans `foulfix_mvp/` ;
- `Foul-Fix-GDrive.desktop` utilise maintenant cette icône personnalisée ;
- l'installateur du raccourci Bureau reprend aussi cette même icône si tu relances `installer_bouton_foulfix_GDRIVE.sh`.


## v2.3.152 — Icônes rangées dans assets
- déplace `start_foulfix_icon.png` dans `assets/` ;
- déplace `stop_foulfix_icon.png` dans `assets/` ;
- met à jour les deux fichiers `.desktop` ;
- met à jour l'installateur du raccourci Bureau.


## v2.3.153 — Salutation client corrigée
- le bouton Message/SMS côté Clients n'utilise plus l'adresse e-mail comme nom ;
- priorité désormais au prénom, puis au nom, puis à l'entreprise ;
- si aucun vrai nom n'est disponible, le message commence simplement par « Bonjour, ».


## v2.3.154 — Structure WOPR public / private

```text
Foul-Fix/
├── Foul-Fix.desktop
├── Arreter-Foul-Fix.desktop
└── WOPR/
    ├── public/
    │   ├── app.py
    │   ├── templates/
    │   ├── static/
    │   ├── assets/
    │   ├── scripts/
    │   ├── requirements.txt
    │   └── README.md
    └── private/
        ├── data/
        ├── assets/
        ├── seeds/
        └── signatures/
```

`public/` contient le code partageable. `private/` contient les données locales et sensibles.
Au premier lancement, si l'ancien dossier `foulfix_mvp/` est encore présent à côté de `WOPR/`,
les données privées sont **copiées** vers `WOPR/private/`. L'ancien dossier n'est jamais supprimé ni déplacé.


## v2.3.155 — Correctif lancement WOPR
- corrige les deux fichiers `.desktop` ;
- suppression de la commande `bash -c ... $0 ... %k` qui empêchait KDE de retrouver correctement la racine ;
- les boutons Start/Stop appellent maintenant directement les scripts WOPR avec le chemin réel `/home/foul/GDrive/Web/Foul-Fix/...` ;
- aucun changement de données ni de structure.


## v2.3.156 — Traductions PDF atelier complétées
- vérification des 53 libellés fixes : EN / UA / ES / DE / IT possèdent tous les mêmes clés que le français ;
- complète le vocabulaire libre des factures dans les 5 langues ;
- corrige notamment « Forfait Repair électronique » et « (soudure/micro-soudure) » ;
- ajoute les termes courants : carte mère, carte électronique, connecteurs HDMI/USB-C/charge, écran, batterie, ventilateur, pâte thermique, métal liquide, SSD, Windows, récupération/sauvegarde de données, virus/malware, main-d’œuvre, alimentation, etc.


## v2.3.157 — Clé maître portable
- WOPR ne crée plus silencieusement une nouvelle `master.key` lorsqu'elle manque ;
- au premier démarrage sur une nouvelle machine, un écran local demande d'importer la clé existante ;
- une option de création reste disponible uniquement pour une vraie nouvelle installation ;
- Paramètres > Sécurité permet d'exporter `master.key` manuellement ;
- la clé reste stockée hors de WOPR dans `~/.config/Foul-Fix/master.key` sous Linux ou `%APPDATA%\Foul-Fix\master.key` sous Windows ;
- l'export est marqué `no-store` pour éviter la mise en cache HTTP.


## v2.3.158 — Discrétion clé maître
- retire entièrement de l'écran Sécurité le statut et l'emplacement de `master.key` ;
- retire le chemin local de la clé de l'écran d'import au premier démarrage ;
- la page normale ne révèle plus qu'une clé maître existe ni où elle est stockée ;
- le mécanisme d'import automatique si la clé manque reste inchangé ;
- le chiffrement Abby / SMTP / mots de passe appareils reste inchangé.

## v2.3.159 — Lanceurs Linux portables
- supprime les chemins `/home/foul/...` des commandes Start/Stop ;
- les deux fichiers `.desktop` retrouvent maintenant leur propre dossier via `%k` ;
- WOPR peut être déplacé sur un autre dossier, disque ou clé USB sans modifier les commandes de lancement ;
- au premier lancement après déplacement, les icônes Start/Stop sont automatiquement recalées vers leur nouvel emplacement ;
- aucune donnée privée n'est déplacée ou modifiée.


## v2.3.160 — Lanceurs Windows portables

Windows a maintenant ses lanceurs natifs :

- `Foul-Fix-Windows.cmd`
- `Arreter-Foul-Fix-Windows.cmd`

Les deux utilisent uniquement l'emplacement courant du dossier `Foul-Fix` : aucun chemin utilisateur n'est codé en dur.

Au premier lancement Windows :
- WOPR cherche Python 3 (`py`, `python` ou `python3`) ;
- crée `WOPR/private/.venv-win` si nécessaire ;
- installe les dépendances depuis `requirements.txt` ;
- lance Flask sans fenêtre de console ;
- écrit le PID et le log dans `WOPR/private/data/` ;
- ouvre automatiquement `http://127.0.0.1:5000`.

La clé maître reste gérée séparément dans le profil local Windows et WOPR demandera son import si elle manque.

KDE Connect reste naturellement une fonction Linux/KDE : son absence sous Windows n'empêche pas le reste de WOPR de fonctionner.

## v2.3.161 — WOPR autonome et déplaçable seul

Le dossier parent `Foul-Fix/` n'est plus requis pour la portabilité. Le dossier `WOPR/` contient désormais ses propres lanceurs Linux et Windows à sa racine.

Les documents gérés par l'application sont désormais stockés dans :
- `WOPR/private/documents/Factures/`
- `WOPR/private/documents/Devis/`

Au premier lancement après cette mise à jour, si d'anciens dossiers `Factures/` et `Devis/` existent juste à côté de WOPR, ils sont **copiés** dans `private/documents/` sans suppression ni écrasement. Les originaux restent intacts.

Une fois cette copie validée, `WOPR/` peut être déplacé seul sur un disque, une clé USB ou une autre machine. Les données, le code et les documents suivent WOPR.


## v2.3.162 — Archive Suivie portable + détection déjà lancé
- `Suivie de réparation` est désormais copié sans écrasement vers `WOPR/private/documents/Suivie de réparation/`.
- La variante `Suivi de réparation` est aussi reconnue lors de la migration.
- Un marker séparé garantit cette migration même si la v2.3.161 avait déjà migré Factures/Devis.
- Linux et Windows signalent maintenant clairement « Foul-Fix est déjà lancé » au lieu de tenter un second démarrage.
- Les dossiers d'origine restent intacts : aucune suppression ni déplacement automatique.


## v2.3.163 — Correction « Suivi de réparation »
- le dossier portable s'appelle désormais correctement `WOPR/private/documents/Suivi de réparation/` ;
- l'application utilise ce chemin corrigé ;
- la migration reconnaît toujours les deux anciens noms `Suivi de réparation` et `Suivie de réparation` comme sources, mais copie toujours vers le nom correct ;
- cette mise à jour reprend aussi la détection « Foul-Fix est déjà lancé » de la v2.3.162, donc la v2.3.162 n'a pas besoin d'être installée avant.

## v2.3.164 — Premier lancement Windows propre
- ajoute `WOPR/Foul-Fix-Windows.vbs` comme lanceur Windows principal sans console noire ;
- le lanceur retrouve WOPR à partir de son propre emplacement, donc reste portable ;
- au premier lancement, WOPR détecte Python 3 puis prépare automatiquement son environnement et ses dépendances ;
- si Python manque, un message clair propose d'ouvrir la page officielle de téléchargement ;
- une information est affichée avant la première préparation, puis une confirmation quand WOPR est prêt ;
- les erreurs d'installation renvoient vers le journal local ;
- aucun changement au lancement Linux dans cette version.


## v2.3.165 — Audit et diagnostic de portabilité
- audit des chemins persistants : données, configuration, imports, sauvegardes, signatures, Factures, Devis et Suivi sont contenus dans `WOPR/private` ;
- création automatique des dossiers privés même lors d'un lancement direct de `app.py` ;
- correction d'un vrai point bloquant : les signatures client ne sont plus enregistrées avec un chemin absolu ; les anciens chemins sont convertis en noms de fichiers dès que possible et restent lisibles après déplacement ;
- ajout dans Sécurité d'un diagnostic de portabilité non sensible : structure, écriture, base, cœur public, chemins personnels codés en dur, lanceurs et dépendances ;
- `kdeconnect-cli` est affiché comme optionnel et ne bloque pas la portabilité ;
- la clé maître reste volontairement séparée du dossier WOPR et son emplacement n'est jamais affiché.


## v2.3.166 — Diagnostic de portabilité non bloquant
- corrige le 500 de `/security` introduit par le diagnostic de portabilité ;
- une vérification incompatible ou défaillante ne peut plus rendre la page Sécurité inaccessible ;
- en cas d'erreur locale, le diagnostic affiche simplement qu'il est indisponible et WOPR continue de fonctionner ;
- aucun chemin local ni secret n'est affiché dans le message d'erreur.


## v2.3.167 — Diagnostic portabilité corrigé
- corrige le faux positif « Chemins propres à ce PC : app.py » : le diagnostic détectait ses propres chaînes de contrôle ;
- retire de l'écran Sécurité la phrase explicative sur la clé de déchiffrement, inutile dans l'interface ;
- aucun autre comportement n'est modifié.


## v2.3.168 — Easter egg WOPR / Tic-Tac-Toe
- 10 clics rapides sur le logo Foul-Fix ouvrent un terminal WOPR caché ;
- morpion jouable contre WOPR, avec IA minimax imbattable ;
- ambiance CRT / 8-bit et bips synthétiques générés par le navigateur ;
- aucun extrait audio du film n'est inclus ;
- tout est côté navigateur et ne touche ni la base ni les données métier.


## v2.3.169 — Easter egg déplacé sur le badge API
- le logo Foul-Fix redevient un lien normal vers l'accueil ;
- l'easter egg WOPR se déclenche désormais avec 10 clics rapides sur `API v...` ;
- le badge API ne provoque aucun rechargement de page pendant la séquence ;
- le logo de barre supérieure est légèrement agrandi en conservant son ratio naturel afin d'éviter l'aspect trop tassé à petite taille.


## v2.3.170 — Easter egg réellement fonctionnel + logo 8-bit détouré
- corrige le bug JavaScript qui empêchait totalement l'initialisation de l'easter egg (`brand` restait référencé après le déplacement vers le badge API) ;
- 10 clics rapides sur le badge `API v...` déclenchent désormais WOPR / Tic-Tac-Toe ;
- le logo 8-bit n'utilise plus le panneau rectangulaire d'origine : fond rendu transparent ;
- suppression du fragment/barre graphique à droite qui donnait l'impression d'un bouton supplémentaire ;
- conservation du logo et du texte en pixel-art.
