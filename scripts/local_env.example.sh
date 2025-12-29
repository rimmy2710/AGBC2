#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=/workspaces/AGBC2/src

# Admin config sheet (not secret)
export ADMIN_CONFIG_SHEET_ID="1LSpeHELAOQw3_kdqcQ9CftWyZ9JZqUGH6EBsmmoEn9w"
export ADMIN_CONFIG_ENABLED=1

# Output sheet (not secret)
export GOOGLE_SHEET_ID="1LSpeHELAOQw3_kdqcQ9CftWyZ9JZqUGH6EBsmmoEn9w"
export GOOGLE_SHEET_TAB="AGBC2 – News Draft"
export GOOGLE_APPLICATION_CREDENTIALS="/home/codespace/.agbc2/secrets/gspread_service_account.json"

# Telegram (secrets - DO NOT COMMIT real values)
export TELEGRAM_SESSION_PATH="/home/codespace/.agbc2/secrets/telegram.session"
export TELEGRAM_API_ID="30864018"
export TELEGRAM_API_HASH="dc97dc8c6734021bb9bf01bba2380426"

# OpenAI (secret - DO NOT COMMIT real values)
export OPENAI_ENABLED=1
export OPENAI_MODEL="gpt-5-nano"
# export OPENAI_API_KEY="OPENAI_KEY_HERE"

# Safe mode
export LIMIT_PER_CHANNEL=50
export STYLE_MAX_EXAMPLES=3
