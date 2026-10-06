#!/usr/bin/env bash
# Start backend (8000) and frontend (5173) together. Ctrl-C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r backend/requirements.txt

cd "$ROOT/frontend"
[ -d node_modules ] || npm install

cd "$ROOT"
uvicorn app.main:app --app-dir backend --reload --port 8000 &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT

cd "$ROOT/frontend"
npm run dev
