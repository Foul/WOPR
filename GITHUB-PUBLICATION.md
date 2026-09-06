# Publication GitHub - checklist WOPR

Avant chaque push public :

- [ ] `private/` absent
- [ ] aucune base `*.db`
- [ ] aucune sauvegarde SQLite
- [ ] aucun `master.key`
- [ ] aucune clé API / jeton SMTP / secret Google
- [ ] aucune facture, devis ou suivi client réel
- [ ] aucune signature client
- [ ] aucune capture contenant des données réelles
- [ ] `.venv/`, caches et logs exclus
- [ ] documentation mise à jour
- [ ] version vérifiée

Le fichier `.gitignore` fourni avec ce pack ajoute des protections adaptées à une publication publique.
