# WOPR - Manuel utilisateur

**Version documentée : 2.3.285**
**Documentation mise à jour : 11 septembre 2026**

## 1. Présentation
WOPR signifie **Workflow d’Organisation et de Pilotage des Réparations**. C’est une application locale de gestion d’atelier centralisant réception, suivi, clients, devis, factures, encaissements, restitutions, documents, achats et administratif.

WOPR est distribué gratuitement par Foul-Fix et publié sous licence **GNU GPLv3**.

Plateformes officielles : Linux et Windows. macOS n’est pas supporté.

## 2. Principes
- application web locale dans le navigateur ;
- données privées séparées dans `private/` ;
- identité d’entreprise configurable localement ;
- Suivi = source de vérité du CA ;
- PDF = justificatifs, pas source de recalcul comptable ;
- Google Contacts, Abby, SMTP Proton et KDE Connect sont optionnels.

## 3. Démarrage
Le paquet fournit `WOPR` sous Linux et `WOPR.exe` sous Windows. Le lanceur unifié contrôle les dépendances, évite les doubles démarrages, lance le serveur puis ouvre le navigateur.

Accès local habituel : `http://127.0.0.1:5000`.

Les sauvegardes automatiques sont intelligentes : pas de duplication inutile au démarrage et sauvegarde d’arrêt uniquement si la base a changé.

## 4. Navigation et thèmes
Navigation : Atelier, Recherche globale, Suivi, Factures, Facture simple, Devis, Clients, Achats / Ventes, Antivirus, Abby, Sécurité, CA / Déclarations et Verrouiller.

Thèmes : **Normal**, **Dark**, **WOPR / Terminal**, **8-BIT**.

Palette d’actions :
- bleu : ouvrir, historique, PDF, impression ;
- vert : envoyer, enregistrer, valider ;
- ambre : modifier ;
- violet : dossier, joindre, fusionner, action spéciale ;
- rouge : supprimer.

Le thème **8-BIT** applique un skin pixel-art aux actions, y compris aux boutons ajoutés dynamiquement, et harmonise légèrement tableaux et badges.

## 5. Atelier
Le tableau de bord présente dossiers actifs, réparations à surveiller, matériels à restituer, impayés, CA encaissé, activité mensuelle et dossiers anciens à relancer.

## 6. Nouvelle réparation
Un client existant peut être recherché puis repris automatiquement. L’aide code postal → ville utilise une base locale et propose les communes possibles sans sélection arbitraire.

## 7. Suivi
Le Suivi centralise dossiers par année/mois, recherche, filtres, facturation, encaissement et export CSV.

Les tableaux larges sont adaptés aux grands écrans avec défilement horizontal. La légende suit la largeur réelle du tableau.

Les boutons PDF et **Dossier** donnent un accès direct aux documents et à leur répertoire d’archive.

## 8. Factures
La page Factures permet modification, PDF multilingue, impression, envoi par e-mail et ouverture du dossier d’archive.

Les PDF sont affichés inline pour éviter les téléchargements automatiques inutiles.

Classement : `private/documents/Factures/YYYY/MM - Mois/`.

## 9. Devis
Création, modification, PDF, originaux, envoi, dossier et suppression. Les annexes d’un même devis restent rattachées au devis concerné.

## 10. Clients
Recherche, historique, SMS/message, modification, fusion, archivage/suppression volontaire, import/export et Google Contacts.

La synchronisation Google est manuelle et non destructive. Les actions WOPR → Google et Google → WOPR restent explicites ; une progression et un résumé final sont affichés.

La recherche et la ligne courante sont conservées après édition.

## 11. Recherche globale
Recherche multi-mots insensible à la casse, aux accents et à la ponctuation sur clients, dossiers, appareils, diagnostics, factures, devis et Achats / Ventes.

## 12. Achats / Ventes
Ajout, recherche, édition directe, suppression, rattachement de justificatif, ouverture du document et du dossier.

Factures fournisseurs : `private/documents/Fournisseurs/YYYY/MM - Mois/`.

La résolution privilégie le numéro de facture, le nom d’origine, les anciens chemins cohérents puis des recherches fournisseur/date contrôlées.

## 13. Abby
Intégration optionnelle pour configuration API, tests, synchronisation et import de factures fournisseurs électroniques.

## 14. Antivirus
Le registre Antivirus mémorise client, dates, produit, expiration, facture et informations de licence.

Actions : Ajouter/Valider, Éditer, Annuler, Supprimer. En thème 8-BIT elles suivent la même palette pixel-art que le reste.

## 15. CA / Déclarations
Le CA officiel provient du Suivi et des dates d’encaissement. Les PDF ne recalculent pas le CA.

## 16. Communication client
Les messages utilisent un salut neutre `Bonjour,` et peuvent être préparés depuis les dossiers ou fiches clients.

## 17. Documents
Classement automatique :
- Suivi : `private/documents/Suivi de réparation/YYYY/MM - Mois/`
- Factures : `private/documents/Factures/YYYY/MM - Mois/`
- Devis : `private/documents/Devis/`
- Fournisseurs : `private/documents/Fournisseurs/YYYY/MM - Mois/`

## 18. Publication
`Update-WOPR.sh` contrôle les données sensibles, vérifie la version, pousse GitHub, synchronise la documentation et génère les notes de release depuis `docs/CHANGELOG-DOC.md`.

## 19. Licence et support
Linux et Windows sont supportés. macOS n’est pas supporté.

WOPR est 100 % gratuit. Soutien facultatif : `https://paypal.me/foul`.

## 20. Crédit
Développé par Foul-Fix, avec l’aide de ChatGPT (OpenAI) pour l’assistance au développement, à la documentation et aux tests.
