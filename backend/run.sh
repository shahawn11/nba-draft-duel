#!/usr/bin/env bash
# Launch the NBA Draft Duel backend from the clean arm64 venv with a sanitized
# environment. This host leaks PYTHONPATH (toolbox python3.10) into venvs, which
# breaks C-extension packages; clearing it forces the venv's own arm64 wheels.
# See README "Troubleshooting" for the full story.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv312/bin/python" ]; then
  echo "Missing .venv312. Create it first:"
  echo "  PY=/Users/shahawn/.local/share/mise/installs/python/3.12.13/bin/python3"
  echo "  env PYTHONPATH= \$PY -m venv .venv312"
  echo "  env PYTHONPATH= ./.venv312/bin/python -m pip install -r requirements.txt"
  exit 1
fi

exec env PYTHONPATH= ./.venv312/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port "${PORT:-8000}" "$@"
