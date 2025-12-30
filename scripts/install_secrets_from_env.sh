#!/usr/bin/env bash
set -euo pipefail

AGBC2_HOME="${AGBC2_HOME:-$HOME/.agbc2}"
AGBC2_SECRETS_DIR="${AGBC2_SECRETS_DIR:-$AGBC2_HOME/secrets}"

# gspread stores token here sometimes; keep default under $HOME
GSPREAD_DIR="${GSPREAD_DIR:-$HOME/.config/gspread}"

mkdir -p "$AGBC2_SECRETS_DIR" "$GSPREAD_DIR"

# Google service account json (base64)
if [[ -n "${GSPREAD_SA_JSON_B64:-}" ]]; then
  echo "$GSPREAD_SA_JSON_B64" | base64 -d > "$AGBC2_SECRETS_DIR/gspread_service_account.json"
  echo "[AGBC2] wrote $AGBC2_SECRETS_DIR/gspread_service_account.json"
fi

# Telegram: we're using TELEGRAM_STRING_SESSION => no file needed here.
# (If you later want session file mode, add it explicitly.)

