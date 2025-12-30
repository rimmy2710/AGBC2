#!/usr/bin/env bash
set -euo pipefail

SECRETS_DIR="/home/codespace/.agbc2/secrets"
GSPREAD_DIR="/home/codespace/.config/gspread"

mkdir -p "$SECRETS_DIR" "$GSPREAD_DIR"

decode_b64_to_file() {
  local var_name="$1"
  local out_path="$2"

  local val="${!var_name:-}"
  if [[ -z "$val" ]]; then
    return 0
  fi

  # remove all whitespace/newlines to avoid "base64: invalid input"
  val="$(printf "%s" "$val" | tr -d '\n\r\t ')"

  if ! printf "%s" "$val" | base64 -d > "$out_path" 2>/dev/null; then
    echo "[AGBC2] WARNING: invalid base64 in ${var_name} (skip)"
    rm -f "$out_path" || true
    return 0
  fi

  echo "[AGBC2] installed $(basename "$out_path") from env"
}

# gspread service account json
decode_b64_to_file "GSPREAD_SA_JSON_B64" "$SECRETS_DIR/gspread_service_account.json"
if [[ -f "$SECRETS_DIR/gspread_service_account.json" ]]; then
  chmod 600 "$SECRETS_DIR/gspread_service_account.json"
  ln -sf "$SECRETS_DIR/gspread_service_account.json" "$GSPREAD_DIR/service_account.json"
fi

# telegram session
decode_b64_to_file "TELEGRAM_SESSION_B64" "$SECRETS_DIR/telegram.session"
if [[ -f "$SECRETS_DIR/telegram.session" ]]; then
  chmod 600 "$SECRETS_DIR/telegram.session"
fi

# Optional sanity prints (no secret values)
[[ -f "$SECRETS_DIR/gspread_service_account.json" ]] && echo "[AGBC2] gspread_sa_present=1" || echo "[AGBC2] gspread_sa_present=0"
[[ -f "$SECRETS_DIR/telegram.session" ]] && echo "[AGBC2] telegram_session_present=1" || echo "[AGBC2] telegram_session_present=0"
