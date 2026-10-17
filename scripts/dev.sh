#!/usr/bin/env bash
# Run backend (http://localhost:8000) and frontend (http://localhost:5173) together.
# Installs missing deps first; Ctrl-C stops both.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
command -v uv >/dev/null || { echo "uv not found: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v pnpm >/dev/null || { echo "pnpm not found: https://pnpm.io/installation" >&2; exit 1; }

[ -d "$root/backend/.venv" ] || (cd "$root/backend" && uv sync)
[ -d "$root/frontend/node_modules" ] || (cd "$root/frontend" && pnpm install)

back="" front=""
cleanup() {
  trap - INT TERM EXIT
  # Kill each server's whole process group (uvicorn --reload and vite spawn children).
  for pid in $back $front; do kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

set -m # job control: each background job gets its own process group
(cd "$root/backend" && exec uv run uvicorn app.main:app --reload --port 8000) &
back=$!
(cd "$root/frontend" && exec pnpm dev --port 5173 --strictPort) &
front=$!
set +m

# Stop both as soon as either server dies (polling: macOS bash 3.2 has no `wait -n`).
while kill -0 "$back" 2>/dev/null && kill -0 "$front" 2>/dev/null; do sleep 1; done
