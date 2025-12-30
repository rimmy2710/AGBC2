#!/usr/bin/env bash
set -euo pipefail

SECRETS_DIR="/home/codespace/.agbc2/secrets"
GSPREAD_DIR="/home/codespace/.config/gspread"

mkdir -p "$SECRETS_DIR"
mkdir -p "$GSPREAD_DIR"

_decode_b64_to_file() {
  # $1 = env var name, $2 = output file path
  local var_name="$1"
  local out_path="$2"
  local tmp_path="${out_path}.tmp"

  # indirect expansion to get env var value
  local val="${!var_name:-}"
  if [[ -z "$val" ]]; then
    return 0
  fi

  # Use printf (not echo) and ignore non-base64 chars (-i) to tolerate CRLF/whitespace
  if ! printf '%s' "$val" | base64 -d -i > "$tmp_path" 2>/dev/null; then
    rm -f "$tmp_path"
    echo "[AGBC2] WARNING: invalid base64 in ${var_name} (skip)" >&2
    return 0
  fi

  chmod 600 "$tmp_path"
  mv -f "$tmp_path" "$out_path"
}

# Write gspread service account json from base64 secret
_decode_b64_to_file "GSPREAD_SA_JSON_B64" "$SECRETS_DIR/gspread_service_account.json"
if [[ -f "$SECRETS_DIR/gspread_service_account.json" ]]; then
  ln -sf "$SECRETS_DIR/gspread_service_account.json" "$GSPREAD_DIR/service_account.json"
  echo "[AGBC2] installed gspread_service_account.json from env"
fi

# Write telegram session from base64 secret
_decode_b64_to_file "TELEGRAM_SESSION_B64" "$SECRETS_DIR/telegram.session"
if [[ -f "$SECRETS_DIR/telegram.session" ]]; then
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
