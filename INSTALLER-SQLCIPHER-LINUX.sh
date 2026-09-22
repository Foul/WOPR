#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/private/.venv"
REQ="$ROOT/public/requirements.txt"

if [[ ! -f "$REQ" ]]; then
  echo "ERREUR: public/requirements.txt introuvable."
  exit 1
fi

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Création de l'environnement Python WOPR..."
  python3 -m venv "$VENV"
fi

echo "Installation / vérification des dépendances WOPR + SQLCipher..."
"$VENV/bin/python" -m pip install -r "$REQ"

echo "Test SQLCipher Python..."
"$VENV/bin/python" - <<'PY'
from sqlcipher3 import dbapi2 as sqlite3
con = sqlite3.connect(":memory:")
con.execute("PRAGMA key='wopr-test'")
version = con.execute("PRAGMA cipher_version").fetchone()
con.close()
if not version or not version[0]:
    raise SystemExit("SQLCipher chargé mais version introuvable")
print("SQLCipher OK :", version[0])
PY

echo
echo "OK. Tu peux lancer WOPR normalement avec ./WOPR"
