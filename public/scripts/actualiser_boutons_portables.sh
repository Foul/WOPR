#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLIC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ASSETS_DIR="$PUBLIC_DIR/assets"
ICON_DIR="$HOME/.local/share/icons"

mkdir -p "$ICON_DIR"

[ -f "$ASSETS_DIR/start_wopr_icon.png" ] && cp -f "$ASSETS_DIR/start_wopr_icon.png" "$ICON_DIR/wopr-start.png"
[ -f "$ASSETS_DIR/stop_wopr_icon.png" ] && cp -f "$ASSETS_DIR/stop_wopr_icon.png" "$ICON_DIR/wopr-stop.png"

command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$ICON_DIR" >/dev/null 2>&1 || true
exit 0
