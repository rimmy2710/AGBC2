#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# AGBC2 portable paths (Codespaces + GitHub Actions)
# ============================================================
HOME_DIR="${HOME:-/home/runner}"
AGBC2_HOME="${AGBC2_HOME:-$HOME_DIR/.agbc2}"
AGBC2_SECRETS_DIR="${AGBC2_SECRETS_DIR:-$AGBC2_HOME/secrets}"
AGBC2_LOG_DIR="${AGBC2_LOG_DIR:-$AGBC2_HOME/logs}"
GSPREAD_DIR="${GSPREAD_DIR:-$HOME_DIR/.config/gspread}"

mkdir -p "$AGBC2_SECRETS_DIR" "$AGBC2_LOG_DIR" "$GSPREAD_DIR"

export AGBC2_HOME AGBC2_SECRETS_DIR AGBC2_LOG_DIR GSPREAD_DIR

echo "[AGBC2] bootstrap starting..."
echo "[AGBC2] AGBC2_HOME=$AGBC2_HOME"

# Ensure src is on PYTHONPATH
export PYTHONPATH="${PYTHONPATH:-$(pwd)/src}"

# Load env defaults (safe if missing)
if [[ -f scripts/env_from_codespaces.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/env_from_codespaces.sh
fi

# Restore secrets from env (base64) if provided
if [[ -f scripts/install_secrets_from_env.sh ]]; then
  if [[ -n "${GSPREAD_SA_JSON_B64:-}" || -n "${TELEGRAM_SESSION_B64:-}" ]]; then
    bash scripts/install_secrets_from_env.sh
  fi
fi

# Optional local env (NOT committed)
if [[ -f scripts/local_env.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/local_env.sh
  echo "[AGBC2] loaded scripts/local_env.sh"
fi

# gspread service account symlink (portable)
if [[ -f "$AGBC2_SECRETS_DIR/gspread_service_account.json" ]]; then
  ln -sf "$AGBC2_SECRETS_DIR/gspread_service_account.json" \
    "$GSPREAD_DIR/service_account.json"
  chmod 600 "$AGBC2_SECRETS_DIR/gspread_service_account.json" || true
  echo "[AGBC2] gspread creds OK"
else
  echo "[AGBC2] WARN: Missing $AGBC2_SECRETS_DIR/gspread_service_account.json"
fi

# Quick import check
python - <<'PY'
import news_agent
print("[AGBC2] import_ok")
PY

# Admin config check
if [[ -n "${ADMIN_CONFIG_SHEET_ID:-}" ]]; then
  python scripts/test_admin_config.py || echo "[AGBC2] WARN: test_admin_config failed"
else
  echo "[AGBC2] WARN: ADMIN_CONFIG_SHEET_ID not set"
fi

# Telegram session check (NO OTP)
if [[ -n "${TELEGRAM_API_ID:-}" && -n "${TELEGRAM_API_HASH:-}" ]]; then
  python scripts/check_telegram_session.py || echo "[AGBC2] WARN: telegram session check failed"
else
  echo "[AGBC2] WARN: Telegram env missing (TELEGRAM_API_ID/HASH)"
fi

# Google Sheet access check
if [[ -n "${GOOGLE_SHEET_ID:-}" ]]; then
  python - <<'PY' || echo "[AGBC2] WARN: cannot open GOOGLE_SHEET_ID (share permission or ID wrong)"
import os, gspread
sid=os.environ["GOOGLE_SHEET_ID"]
tab=os.getenv("GOOGLE_SHEET_TAB","AGBC2 – News Draft")
gc=gspread.service_account()
sh=gc.open_by_key(sid)
ws=sh.worksheet(tab)
print("[AGBC2] sheet_ok:", sh.title)
print("[AGBC2] tab_ok:", ws.title, "rows=", ws.row_count, "cols=", ws.col_count)
PY
else
  echo "[AGBC2] WARN: GOOGLE_SHEET_ID not set"
fi

# OpenAI check (optional)
if [[ "${OPENAI_ENABLED:-0}" == "1" ]]; then
  python scripts/test_ai_writer.py || echo "[AGBC2] WARN: OpenAI test failed"
else
  echo "[AGBC2] OpenAI disabled (OPENAI_ENABLED!=1) - skip OpenAI test"
fi

echo "[AGBC2] bootstrap done."
