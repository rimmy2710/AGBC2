#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# AGBC2 portable paths (Codespaces + GitHub Actions)
# ============================================================
HOME_DIR="${HOME:-/home/runner}"
AGBC2_HOME="${AGBC2_HOME:-$HOME_DIR/.agbc2}"
AGBC2_LOG_DIR="${AGBC2_LOG_DIR:-$AGBC2_HOME/logs}"
AGBC2_SECRETS_DIR="$AGBC2_HOME/secrets"

mkdir -p "$AGBC2_LOG_DIR" "$AGBC2_SECRETS_DIR"

export AGBC2_HOME AGBC2_LOG_DIR AGBC2_SECRETS_DIR

# Timestamp (FIX LỖI CHÍNH)
TS="$(date +%Y%m%d_%H%M%S)"
LOG="$AGBC2_LOG_DIR/run_all_${TS}.log"

echo "[AGBC2] HOME=$HOME_DIR"
echo "[AGBC2] AGBC2_HOME=$AGBC2_HOME"
echo "[AGBC2] AGBC2_LOG_DIR=$AGBC2_LOG_DIR"
echo "[AGBC2] LOG=$LOG"

# Always run from repo root
cd "$(dirname "$0")/.."

# Tee toàn bộ output vào log
exec > >(tee -a "$LOG") 2>&1

# ============================================================
# Load env
# ============================================================
if [[ -f scripts/local_env.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/local_env.sh
fi

export PYTHONPATH="${PYTHONPATH:-/workspaces/AGBC2/src}"

# ============================================================
# Install deps (CI-safe)
# ============================================================
pip install -q -r requirements.txt

# ============================================================
# Bootstrap
# ============================================================
echo "[AGBC2] run_all: bootstrap..."
bash scripts/bootstrap.sh

# ============================================================
# Telegram session sanity check (NO OTP)
# ============================================================
echo "[AGBC2] run_all: check telegram session..."
python scripts/check_telegram_session.py

# ============================================================
# Main pipeline
# ============================================================
echo "[AGBC2] run_all: run_telethon_once..."
PYTHONFAULTHANDLER=1 python -u scripts/run_telethon_once.py

# ============================================================
# Optional self-learning
# ============================================================
if [[ -f scripts/self_learning_once.py ]]; then
  echo "[AGBC2] run_all: self_learning_once (optional)..."
  python scripts/self_learning_once.py || true
fi

echo "[AGBC2] run_all: done. log=$LOG"
