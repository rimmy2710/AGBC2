#!/usr/bin/env bash
set -euo pipefail
# Load env defaults for Codespaces
if [[ -f scripts/env_from_codespaces.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/env_from_codespaces.sh
fi


echo "[AGBC2] bootstrap starting..."

# 1) Paths
export PYTHONPATH="${PYTHONPATH:-/workspaces/AGBC2/src}"

mkdir -p /home/codespace/.agbc2/secrets
mkdir -p /home/codespace/.agbc2/logs
mkdir -p /home/codespace/.config/gspread
# Restore secrets from Codespaces env (base64) if provided
if [[ -f scripts/install_secrets_from_env.sh ]]; then
  if [[ -n "${GSPREAD_SA_JSON_B64:-}" || -n "${TELEGRAM_SESSION_B64:-}" ]]; then
    bash scripts/install_secrets_from_env.sh
  fi
fi


# 2) Optional local env (NOT committed)
# You create this once locally: scripts/local_env.sh (ignored by git)
if [[ -f scripts/local_env.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/local_env.sh
  echo "[AGBC2] loaded scripts/local_env.sh"
fi

# 3) Ensure gspread service account symlink if file exists
if [[ -f /home/codespace/.agbc2/secrets/gspread_service_account.json ]]; then
  ln -sf /home/codespace/.agbc2/secrets/gspread_service_account.json \
    /home/codespace/.config/gspread/service_account.json
  chmod 600 /home/codespace/.agbc2/secrets/gspread_service_account.json || true
  echo "[AGBC2] gspread creds OK"
else
  echo "[AGBC2] WARN: Missing /home/codespace/.agbc2/secrets/gspread_service_account.json"
fi

# 4) Quick import check
python - <<'PY'
import news_agent
print("[AGBC2] import_ok")
PY

# 5) Check admin config (needs ADMIN_CONFIG_SHEET_ID + gspread creds)
if [[ -n "${ADMIN_CONFIG_SHEET_ID:-}" ]]; then
  python scripts/test_admin_config.py || echo "[AGBC2] WARN: test_admin_config failed"
else
  echo "[AGBC2] WARN: ADMIN_CONFIG_SHEET_ID not set"
fi

# 6) Check Telegram session (needs TELEGRAM_API_ID/HASH/SESSION_PATH)
if [[ -n "${TELEGRAM_API_ID:-}" && -n "${TELEGRAM_API_HASH:-}" && -n "${TELEGRAM_SESSION_PATH:-}" ]]; then
  python scripts/check_telegram_session.py || echo "[AGBC2] WARN: telegram session check failed (may need login)"
else
  echo "[AGBC2] WARN: Telegram env missing (TELEGRAM_API_ID/HASH/SESSION_PATH)"
fi

# 7) Check Google output sheet access (needs GOOGLE_SHEET_ID)
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

# 8) Check OpenAI rewrite (only if enabled)
if [[ "${OPENAI_ENABLED:-0}" == "1" ]]; then
  if python -c "import openai" >/dev/null 2>&1; then
    python scripts/test_ai_writer.py || echo "[AGBC2] WARN: OpenAI test failed (model/key?)"
  else
    echo "[AGBC2] WARN: python package 'openai' missing. Run: pip install openai"
  fi
else
  echo "[AGBC2] OpenAI disabled (OPENAI_ENABLED!=1) - skip OpenAI test"
fi

echo "[AGBC2] bootstrap done."
