cat > scripts/env_from_codespaces.sh <<'EOF'
#!/usr/bin/env bash
# Load runtime env from Codespaces-injected secrets (if present) with sane defaults
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-/workspaces/AGBC2/src}"

# Sheets
: "${GOOGLE_SHEET_ID:=}"
: "${ADMIN_CONFIG_SHEET_ID:=}"
: "${GOOGLE_APPLICATION_CREDENTIALS:=/home/codespace/.agbc2/secrets/gspread_service_account.json}"

# Telegram
: "${TELEGRAM_API_ID:=}"
: "${TELEGRAM_API_HASH:=}"
: "${TELEGRAM_SESSION_PATH:=/home/codespace/.agbc2/secrets/telegram.session}"

# Pipeline toggles
: "${ADMIN_CONFIG_ENABLED:=1}"
: "${LIMIT_PER_CHANNEL:=20}"
: "${STYLE_MAX_EXAMPLES:=5}"

# OpenAI
: "${OPENAI_ENABLED:=0}"
: "${OPENAI_API_KEY:=}"
: "${OPENAI_MODEL:=}"

export GOOGLE_SHEET_ID ADMIN_CONFIG_SHEET_ID GOOGLE_APPLICATION_CREDENTIALS
export TELEGRAM_API_ID TELEGRAM_API_HASH TELEGRAM_SESSION_PATH
export ADMIN_CONFIG_ENABLED LIMIT_PER_CHANNEL STYLE_MAX_EXAMPLES
export OPENAI_ENABLED OPENAI_API_KEY OPENAI_MODEL
EOF

chmod +x scripts/env_from_codespaces.sh
