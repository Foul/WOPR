#!/usr/bin/env bash
set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLIC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WOPR_DIR="$(cd "$PUBLIC_DIR/.." && pwd)"
ROOT_DIR="$(cd "$WOPR_DIR/.." && pwd)"
PRIVATE_DIR="$WOPR_DIR/private"

# Répare automatiquement les icônes absolues après déplacement du dossier.
"$SCRIPT_DIR/actualiser_boutons_portables.sh" >/dev/null 2>&1 || true
DATA_DIR="$PRIVATE_DIR/data"
URL="http://127.0.0.1:5000"
LOG_FILE="$DATA_DIR/wopr-launcher.log"
PID_FILE="$DATA_DIR/wopr.pid"

BACKGROUND_MODE=0
if [ "${1:-}" = "--background" ]; then
    BACKGROUND_MODE=1
fi

mkdir -p "$DATA_DIR" "$PRIVATE_DIR/assets" "$PRIVATE_DIR/seeds" "$PRIVATE_DIR/signatures"

OLD_DIR="$ROOT_DIR/foulfix_mvp"
MIGRATION_MARKER="$PRIVATE_DIR/.migration_from_foulfix_mvp_done"
if [ ! -f "$MIGRATION_MARKER" ] && [ -d "$OLD_DIR" ]; then
    "$SCRIPT_DIR/migrer_depuis_foulfix_mvp.sh" "$OLD_DIR" >/dev/null 2>&1 || true
fi

cd "$PUBLIC_DIR" || exit 1

if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "$URL" >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
    exit 0
fi

PYTHON="$PRIVATE_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        command -v notify-send >/dev/null 2>&1 && notify-send "WOPR" "Python 3 est introuvable."
        exit 1
    fi
    python3 -m venv "$PRIVATE_DIR/.venv" || exit 1
    PYTHON="$PRIVATE_DIR/.venv/bin/python"
    "$PYTHON" -m pip install --upgrade pip >> "$LOG_FILE" 2>&1
    "$PYTHON" -m pip install -r "$PUBLIC_DIR/requirements.txt" >> "$LOG_FILE" 2>&1 || exit 1
fi

if ! "$PYTHON" - <<'PYLIBS' >/dev/null 2>&1
import flask
import reportlab
import qrcode
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
PYLIBS
then
    "$PYTHON" -m pip install -r "$PUBLIC_DIR/requirements.txt" >> "$LOG_FILE" 2>&1 || exit 1
fi

if [ "$BACKGROUND_MODE" -eq 1 ]; then
    {
        echo
        echo "===== $(date '+%Y-%m-%d %H:%M:%S') — démarrage WOPR ====="
    } >> "$LOG_FILE"

    if command -v setsid >/dev/null 2>&1; then
        setsid "$PYTHON" "$PUBLIC_DIR/app.py" >> "$LOG_FILE" 2>&1 < /dev/null &
    else
        nohup "$PYTHON" "$PUBLIC_DIR/app.py" >> "$LOG_FILE" 2>&1 < /dev/null &
    fi

    APP_PID=$!
    echo "$APP_PID" > "$PID_FILE"

    (
        for _ in $(seq 1 40); do
            if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "$URL" >/dev/null 2>&1; then
                xdg-open "$URL" >/dev/null 2>&1 || true
                exit 0
            fi
            sleep 0.25
        done
        command -v notify-send >/dev/null 2>&1 && notify-send "WOPR" "Le serveur n'a pas répondu. Consulte WOPR/private/data/wopr-launcher.log"
    ) >/dev/null 2>&1 &
    exit 0
fi

"$PYTHON" "$PUBLIC_DIR/app.py" 2>&1 | tee "$LOG_FILE"
exit "${PIPESTATUS[0]}"
