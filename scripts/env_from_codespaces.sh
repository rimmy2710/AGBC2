cat > scripts/env_from_codespaces.sh <<'SH'
#!/usr/bin/env bash
# Load runtime env with sane defaults for BOTH Codespaces and GitHub Actions
set -euo pipefail

# Base dir for runtime secrets/logs (portable)
export AGBC2_HOME="${AGBC2_HOME:-$HOME/.agbc2}"
export AGBC2_LOG_DIR="${AGBC2_LOG_DIR:-$AGBC2_HOME/logs}"

mkdir -p "$AGBC2_HOME" "$AGBC2_LOG_DIR" "$AGBC2_HOME/secrets"

export PYTHONPATH="${PYTHONPATH:-$(pwd)/src}"

# Sheets
: "${GOOGLE_SHEET_ID:=}"
: "${ADMIN_CONFIG_SHEET_ID:=}"
: "${GOOGLE_APPLICATION_CREDENTIALS:=$AGBC2_HOME/secrets/gspread_service_account.json}"

# Telegram
: "${TELEGRAM_API_ID:=}"
: "${TELEGRAM_API_HASH:=}"
: "${TELEGRAM_SESSION_PATH:=$AGBC2_HOME/secrets/telegram.session}"
: "${TELEGRAM_STRING_SESSION:=}"

# Pipeline toggles
: "${ADMIN_CONFIG_ENABLED:=1}"
: "${LIMIT_PER_CHANNEL:=20}"
: "${STYLE_MAX_EXAMPLES:=5}"

# OpenAI
: "${OPENAI_ENABLED:=0}"
: "${OPENAI_API_KEY:=}"
: "${OPENAI_MODEL:=}"

export GOOGLE_SHEET_ID ADMIN_CONFIG_SHEET_ID GOOGLE_APPLICATION_CREDENTIALS
export TELEGRAM_API_ID TELEGRAM_API_HASH TELEGRAM_SESSION_PATH TELEGRAM_STRING_SESSION
export ADMIN_CONFIG_ENABLED LIMIT_PER_CHANNEL STYLE_MAX_EXAMPLES
export OPENAI_ENABLED OPENAI_API_KEY OPENAI_MODEL
SH

chmod +x scripts/env_from_codespaces.sh
