#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLIC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PRIVATE_DIR="$(cd "$SCRIPT_DIR/../../private" && pwd)"
APP_PATH="$PUBLIC_DIR/app.py"
PID_FILE="$PRIVATE_DIR/data/wopr.pid"

"$SCRIPT_DIR/actualiser_boutons_portables.sh" >/dev/null 2>&1 || true

PIDS=""

# PID connu.
if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        PIDS="$PID"
    fi
fi

# Récupère aussi toute autre instance Python lançant exactement CE app.py.
for proc in /proc/[0-9]*; do
    [ -r "$proc/cmdline" ] || continue
    cmd="$(tr '\0' ' ' < "$proc/cmdline" 2>/dev/null || true)"
    case "$cmd" in
        *"$APP_PATH"*)
            pid="${proc##*/}"
            case " $PIDS " in
                *" $pid "*) ;;
                *) PIDS="$PIDS $pid" ;;
            esac
            ;;
    esac
done

if [ -z "${PIDS// /}" ]; then
    rm -f "$PID_FILE"
    command -v notify-send >/dev/null 2>&1 && notify-send "WOPR" "WOPR est déjà arrêté."
    exit 0
fi

# Arrêt propre d'abord.
for pid in $PIDS; do
    kill "$pid" 2>/dev/null || true
done

for _ in $(seq 1 20); do
    alive=0
    for pid in $PIDS; do
        if kill -0 "$pid" 2>/dev/null; then
            alive=1
        fi
    done
    [ "$alive" -eq 0 ] && break
    sleep 0.15
done

# Puis force uniquement les instances de CE WOPR qui résistent.
for pid in $PIDS; do
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi
done

# V2.3.211 — une fois le serveur réellement arrêté, capture le dernier état
# SQLite de la session avec la même API de sauvegarde que WOPR.
BACKUP_OK=0
BACKUP_PATH=""
PYTHON_BIN="$PRIVATE_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3 2>/dev/null || true)"
fi
if [ -n "$PYTHON_BIN" ] && [ -f "$APP_PATH" ]; then
    BACKUP_PATH="$("$PYTHON_BIN" "$APP_PATH" --backup-arret 2>/dev/null | tail -n 1)"
    [ -n "$BACKUP_PATH" ] && [ -f "$BACKUP_PATH" ] && BACKUP_OK=1
fi

rm -f "$PID_FILE"
if command -v notify-send >/dev/null 2>&1; then
    if [ "$BACKUP_OK" -eq 1 ]; then
        notify-send "WOPR" "WOPR arrêté. Sauvegarde créée : $(basename "$BACKUP_PATH")"
    else
        notify-send "WOPR" "WOPR arrêté, mais la sauvegarde de fermeture a échoué."
    fi
fi
exit 0
