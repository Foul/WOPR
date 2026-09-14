<p align="center">
  <img src="docs/images/wopr-logo.png" alt="WOPR" width="260">
  <img src="docs/images/wopr-terminal.png" alt="WOPR Terminal" width="260">
</p>

# WOPR

**Workflow d’Organisation et de Pilotage des Réparations**

**100 % gratuit et open source - GNU GPLv3**

WOPR est une application locale de gestion d’atelier pour suivre réparations, clients, devis, factures, encaissements, restitutions, achats, justificatifs et tâches administratives.

**Version documentée : 2.3.286**

> Développé par Foul-Fix, avec l’aide de ChatGPT (OpenAI) pour l’assistance au développement, à la documentation et aux tests.

## Plateformes
- **Linux : supporté** - binaire officiel `WOPR`.
- **Windows : supporté** - binaire officiel `WOPR.exe`.
- **macOS : non supporté** - aucun binaire officiel, aucun test de compatibilité et aucun support garanti.

## Release 2.3.286
- workflow **prise en charge → suivi → facturation → restitution** fiabilisé ;
- recherche client privée et permissive, sans exposer tout le carnet dans la page ;
- création directe d’un client depuis **Clients**, avec aide code postal → ville ;
- synchronisation Google plus prudente : pas de faux « À synchroniser » et aucune écriture automatique ;
- **Facture simple** alignée sur la recherche client principale et remplissage automatique des coordonnées ;
- désignation de facture préremplie depuis le suivi, sans écraser les informations techniques ;
- remise papier par défaut : **Facture + Suivi Papier** ;
- signature e-mail commune intégrée à tous les envois SMTP de WOPR ;
- suppression d’un client relié à Abby propagée côté Abby avant suppression/archivage local ;
- sélection de la base SQLite renforcée par analyse du contenu réel ;
- titres PDF et affichage des anciennes factures nettoyés ;
- corrections d’ergonomie et de cohérence des thèmes, dont **8-BIT**.

## Documentation
- [Manuel Markdown](docs/manuel.md)
- [Documentation HTML](docs/documentation.html)
- [Présentation WOPR](docs/index.html)
- [Manuel PDF](docs/WOPR-Manuel.pdf)
- [Licence, support et dons](docs/LICENCE-SUPPORT.md)
- [Changelog documentation](docs/CHANGELOG-DOC.md)

## Confidentialité
Le dossier **`private/` ne doit jamais être publié**.

## Licence
WOPR est distribué gratuitement par Foul-Fix et publié sous licence **GNU GPLv3**.

## Soutenir WOPR
Soutien facultatif : **https://paypal.me/foul**. Aucun don ne débloque de fonctionnalité.
