# WOPR 2.3.286

## Release - 14 septembre 2026

Cette version consolide surtout le workflow quotidien de l’atelier et les intégrations déjà présentes.

### Clients
- Recherche client côté serveur, plus permissive et sans chargement du carnet complet dans la page.
- Création directe d’un client depuis **Clients**, sans passer par un suivi ou une facture.
- Aide locale code postal → ville dans la fiche client.
- Une fiche simplement réutilisée ne passe plus à tort en « À synchroniser ».
- Les modifications Google restent volontaires et manuelles.

### Prise en charge / suivi
- Suppression du Mode Client automatique lors d’une nouvelle réparation.
- Conservation du PIN/session atelier normal.
- Meilleure cohérence des fiches société / contact.

### Facturation
- Désignation préremplie depuis le suivi.
- Conservation du travail effectué et des informations techniques.
- **Facture + Suivi Papier** par défaut pour une facturation normale.
- **Suivi Papier** uniquement pour le cas spécial « laissé pour pièces ».
- Date comptable renseignée seulement lorsque le paiement est déclaré reçu.
- Facture simple alignée sur la recherche client principale.

### E-mail
- Signature commune appliquée aux envois SMTP de suivi, devis et factures.
- Image de signature intégrée inline et stockée dans `private/`.

### Abby
- Synchronisation et liaison clients conservées.
- Lorsqu’un client relié à Abby est supprimé dans WOPR, WOPR tente d’abord la suppression correspondante chez Abby.
- En cas d’échec Abby, la suppression locale est arrêtée afin d’éviter un décalage silencieux.

### Fiabilité
- Sélection plus sûre de la base SQLite par contenu réel.
- Nettoyage de titres PDF historiques.
- Ajustements de cohérence visuelle et du thème 8-BIT.
