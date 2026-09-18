#!/usr/bin/env bash
set -euo pipefail
# Prefer absolute PYTHON_BIN from caller (Windows-safe); else detect venv.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
if [[ -n "${PYTHON_BIN:-}" && -x "$PYTHON_BIN" ]]; then
  :
elif [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
  PYTHON_BIN="$ROOT/.venv/Scripts/python.exe"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
else
  echo "ERROR: no venv python; run: uv sync --python 3.12" >&2
  exit 1
fi
python3() { "$PYTHON_BIN" "$@"; }
export -f python3
export PYTHON_BIN
export WB_LLM_BASE_URL="${WB_LLM_BASE_URL:-http://127.0.0.1:11434/v1}"
export WB_LLM_API_KEY="${WB_LLM_API_KEY:-ollama}"
echo "Using PYTHON_BIN=$PYTHON_BIN"
bash ./scripts/run.sh --job local-openai-cbc-office-smoke --dry-run
