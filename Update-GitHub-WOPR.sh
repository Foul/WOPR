#!/usr/bin/env bash
set -euo pipefail

# WOPR - Synchronisation GitHub + documentation vers la VM Freebox

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REMOTE="origin"
BRANCH="main"

SITE_USER="Foul"
SITE_HOST="192.168.0.25"
SITE_PORT="22020"
SITE_PATH="/var/www/foul-fix/wopr/"

echo
echo "============================================================"
echo " WOPR -> GitHub + documentation site"
echo "============================================================"
echo

if [ ! -d ".git" ]; then
    echo "ERREUR : ce script doit être placé à la racine de WOPR."
    read -r -p "Entrée pour fermer..."
    exit 1
fi

if [ ! -d "docs" ]; then
    echo "ERREUR : dossier docs/ introuvable."
    read -r -p "Entrée pour fermer..."
    exit 1
fi

# Sécurité : private/ ne doit jamais être suivi par Git.
if git ls-files 'private/*' | grep -q . 2>/dev/null; then
    echo "ERREUR DE SECURITE : private/ contient des fichiers suivis par Git."
    echo "Aucun envoi n'a été effectué."
    read -r -p "Entrée pour fermer..."
    exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    echo "Passage sur la branche $BRANCH..."
    git switch "$BRANCH"
fi

echo "Modifications locales :"
git status --short
echo

git add -A

if ! git diff --cached --quiet; then
    DEFAULT_MSG="Mise à jour WOPR $(date '+%Y-%m-%d %H:%M')"
    read -r -p "Message du commit [$DEFAULT_MSG] : " COMMIT_MSG
    COMMIT_MSG="${COMMIT_MSG:-$DEFAULT_MSG}"
    git commit -m "$COMMIT_MSG"
else
    echo "Aucune modification locale à enregistrer."
fi

echo
echo "Synchronisation GitHub..."
git pull --rebase "$REMOTE" "$BRANCH"
git push "$REMOTE" "$BRANCH"

echo
echo "Synchronisation de docs/ vers la VM Freebox..."
rsync -az --delete \
    -e "ssh -p $SITE_PORT" \
    docs/ \
    "${SITE_USER}@${SITE_HOST}:${SITE_PATH}"

echo
echo "============================================================"
echo " OK"
echo " GitHub       : synchronisé"
echo " GitHub Pages : mise à jour automatique"
echo " Site WOPR    : ${SITE_HOST}:${SITE_PATH}"
echo "============================================================"
echo
git status
echo
read -r -p "Entrée pour fermer..."
