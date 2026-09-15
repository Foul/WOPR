# WOPR 2.3.287

## Release - 15 septembre 2026

Cette version fiabilise le suivi des encaissements, le rapprochement SumUp et les déclarations de chiffre d’affaires.

### CA / déclarations
- Le CA encaissé repose sur une source comptable unique issue du Suivi.
- Les doublons historiques portant la même facture ne sont plus additionnés.
- Les périodes comptables validées restent figées même lorsqu’une preuve de paiement est enrichie plus tard.
- Les rattachements SumUp historiques corrigés ne déplacent plus silencieusement les recettes déjà déclarées.
- Les corrections manuelles affichent leur valeur automatique de comparaison.
- La page CA distingue désormais le cumul des mois précédents, le mois en cours et le total annuel.

### Factures / encaissements
- Les factures historiques remplacées restent consultables sans compter deux fois leur encaissement.
- Les factures orphelines et transactions SumUp disposent de vues de contrôle dédiées.
- Les confirmations, dont « facture modifiée », se ferment automatiquement après quelques secondes tout en restant fermables immédiatement.

### Fiabilité
- Contrôles renforcés des archives, des lignes de facture et des rattachements.
- Aucun PDF ou justificatif ne modifie à lui seul le CA comptable.
