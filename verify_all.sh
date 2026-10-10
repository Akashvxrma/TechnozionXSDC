#!/bin/bash
# Runner script for Technozion SDC Games Verification Suite
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/round_2_sdc_games/www/venv/bin/python3"

if [ -f "$VENV_PYTHON" ]; then
    "$VENV_PYTHON" "$SCRIPT_DIR/verify_all.py" "$@"
else
    python3 "$SCRIPT_DIR/verify_all.py" "$@"
fi
