#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# WOPR - Mise à jour GitHub
# Développé pour le dépôt https://github.com/Foul/WOPR
# ============================================================

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo
echo "============================================================"
echo "   WOPR -> Mise à jour GitHub"
echo "============================================================"
echo

if [ ! -d ".git" ]; then
    echo "ERREUR : ce script doit être placé à la racine du dossier WOPR"
    echo "         (le dossier qui contient .git, public/, docs/, etc.)"
    echo
    read -r -p "Appuie sur Entrée pour fermer..."
    exit 1
fi

# Sécurité : private/ ne doit JAMAIS être suivi par Git.
if git ls-files --error-unmatch private >/dev/null 2>&1 || \
   git ls-files 'private/*' | grep -q . 2>/dev/null; then
    echo "ERREUR DE SECURITE : des fichiers de private/ sont suivis par Git."
    echo "AUCUN envoi n'a été effectué."
    echo
    read -r -p "Appuie sur Entrée pour fermer..."
    exit 1
fi

# Vérifie que le dépôt distant est bien configuré.
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "ERREUR : aucun dépôt GitHub 'origin' n'est configuré."
    echo
    read -r -p "Appuie sur Entrée pour fermer..."
    exit 1
fi

REMOTE_URL="$(git remote get-url origin)"
echo "Dépôt : $REMOTE_URL"
echo

# On reste sur main.
CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "Branche actuelle : $CURRENT_BRANCH"
    echo "Passage sur la branche main..."
    git switch main
    echo
fi

echo "Vérification des modifications locales..."
git status --short
echo

# Ajout de tous les changements autorisés par .gitignore.
git add -A

# Commit seulement s'il y a quelque chose à enregistrer.
if ! git diff --cached --quiet; then
    DEFAULT_MSG="Mise à jour WOPR $(date '+%Y-%m-%d %H:%M')"
    echo "Des modifications vont être enregistrées."
    read -r -p "Message du commit [$DEFAULT_MSG] : " COMMIT_MSG
    COMMIT_MSG="${COMMIT_MSG:-$DEFAULT_MSG}"
    git commit -m "$COMMIT_MSG"
    echo
else
    echo "Aucune modification locale à enregistrer."
    echo
fi

echo "Récupération des éventuelles modifications présentes sur GitHub..."
git pull --rebase origin main
echo

echo "Envoi vers GitHub..."
git push origin main
echo

echo "============================================================"
echo "   OK - WOPR est synchronisé avec GitHub."
echo "   GitHub Pages se mettra à jour automatiquement si docs/ a changé."
echo "============================================================"
echo

git status
echo
read -r -p "Appuie sur Entrée pour fermer..."
