#!/usr/bin/env bash
set -euo pipefail

HOME_DIR="${HOME:-/home/runner}"
AGBC2_HOME="${AGBC2_HOME:-$HOME_DIR/.agbc2}"
AGBC2_LOG_DIR="${AGBC2_LOG_DIR:-$AGBC2_HOME/logs}"
AGBC2_SECRETS_DIR="${AGBC2_SECRETS_DIR:-$AGBC2_HOME/secrets}"

mkdir -p "$AGBC2_LOG_DIR" "$AGBC2_SECRETS_DIR"

export AGBC2_HOME AGBC2_LOG_DIR AGBC2_SECRETS_DIR

TS="$(date +%Y%m%d_%H%M%S)"
LOG="$AGBC2_LOG_DIR/run_all_${TS}.log"

echo "[AGBC2] HOME=$HOME_DIR"
echo "[AGBC2] AGBC2_HOME=$AGBC2_HOME"
echo "[AGBC2] AGBC2_LOG_DIR=$AGBC2_LOG_DIR"
echo "[AGBC2] LOG=$LOG"

cd "$(dirname "$0")/.."
exec > >(tee -a "$LOG") 2>&1

SELF_LEARNING_ENABLED="${SELF_LEARNING_ENABLED:-0}"
BOOTSTRAP_ADMIN_CHECK="${BOOTSTRAP_ADMIN_CHECK:-0}"
BOOTSTRAP_SHEET_CHECK="${BOOTSTRAP_SHEET_CHECK:-1}"

export PYTHONPATH="${PYTHONPATH:-/workspaces/AGBC2/src}"

pip install -q -r requirements.txt

echo "[AGBC2] run_all: bootstrap..."
export ADMIN_CHECK_ENABLED="$BOOTSTRAP_ADMIN_CHECK"
export SHEET_CHECK_ENABLED="$BOOTSTRAP_SHEET_CHECK"
bash scripts/bootstrap.sh

echo "[AGBC2] run_all: check telegram session..."
python scripts/check_telegram_session.py

echo "[AGBC2] run_all: run_telethon_once..."
PYTHONFAULTHANDLER=1 python -u scripts/run_telethon_once.py

if [[ "$SELF_LEARNING_ENABLED" == "1" && -f scripts/self_learning_once.py ]]; then
  echo "[AGBC2] run_all: self_learning_once (optional)..."
  python scripts/self_learning_once.py || true
else
  echo "[AGBC2] run_all: self_learning disabled (SELF_LEARNING_ENABLED!=1)"
fi

echo "[AGBC2] run_all: done. log=$LOG"
