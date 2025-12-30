#!/usr/bin/env bash
set -euo pipefail

# Always run from repo root
cd "$(dirname "$0")/.."

mkdir -p /home/codespace/.agbc2/logs

ts="$(date +%Y%m%d_%H%M%S)"
log="/home/codespace/.agbc2/logs/run_all_${ts}.log"

# Load env (prefer local_env.sh if exists; else rely on Codespaces Secrets env)
if [[ -f scripts/local_env.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/local_env.sh
fi

export PYTHONPATH="${PYTHONPATH:-/workspaces/AGBC2/src}"

# Ensure deps
pip -q install -r requirements.txt >/dev/null

# Bootstrap: restores gspread json from env, checks admin/sheet/openai/telegram auth
echo "[AGBC2] run_all: bootstrap..." | tee -a "$log"
bash ./scripts/bootstrap.sh 2>&1 | tee -a "$log"

# Safety: verify telegram session without OTP prompt
echo "[AGBC2] run_all: check telegram session..." | tee -a "$log"
python scripts/check_telegram_session.py 2>&1 | tee -a "$log"

# Run main pipeline once
echo "[AGBC2] run_all: run_telethon_once..." | tee -a "$log"
PYTHONFAULTHANDLER=1 python -u scripts/run_telethon_once.py 2>&1 | tee -a "$log"

# Optional: self-learning suggestions (won't fail the whole run)
if [[ -f scripts/self_learning_once.py ]]; then
  echo "[AGBC2] run_all: self_learning_once (optional)..." | tee -a "$log"
  PYTHONPATH="$PYTHONPATH" python scripts/self_learning_once.py 2>&1 | tee -a "$log" || true
fi

echo "[AGBC2] run_all: done. log=$log" | tee -a "$log"
