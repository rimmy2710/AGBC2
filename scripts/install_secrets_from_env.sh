#!/usr/bin/env bash
set -euo pipefail

SECRETS_DIR="/home/codespace/.agbc2/secrets"
GSPREAD_DIR="/home/codespace/.config/gspread"

mkdir -p "$SECRETS_DIR"
mkdir -p "$GSPREAD_DIR"

# Write gspread service account json from base64 secret
if [[ -n "${GSPREAD_SA_JSON_B64:-}" ]]; then
  echo "$GSPREAD_SA_JSON_B64" | base64 -d > "$SECRETS_DIR/gspread_service_account.json"
  chmod 600 "$SECRETS_DIR/gspread_service_account.json"
  ln -sf "$SECRETS_DIR/gspread_service_account.json" "$GSPREAD_DIR/service_account.json"
  echo "[AGBC2] installed gspread_service_account.json from env"
fi

# Write telegram session from base64 secret
if [[ -n "${TELEGRAM_SESSION_B64:-}" ]]; then
  echo "$TELEGRAM_SESSION_B64" | base64 -d > "$SECRETS_DIR/telegram.session"
  chmod 600 "$SECRETS_DIR/telegram.session"
  echo "[AGBC2] installed telegram.session from env"
fi

# Optional sanity prints (no secret values)
if [[ -f "$SECRETS_DIR/gspread_service_account.json" ]]; then
  echo "[AGBC2] gspread_sa_present=1"
else
  echo "[AGBC2] gspread_sa_present=0"
fi

if [[ -f "$SECRETS_DIR/telegram.session" ]]; then
  echo "[AGBC2] telegram_session_present=1"
else
  echo "[AGBC2] telegram_session_present=0"
fi
