#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3500}"

if [[ -z "${ALI_QWEN_API_KEY:-}" ]]; then
  echo "❌ Missing env ALI_QWEN_API_KEY"
  exit 1
fi

echo "🔧 Starting backend..."
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

echo "🎨 Building frontend..."
pushd frontend >/dev/null
npm install
npm run build
echo "👀 Preview frontend on :$FRONTEND_PORT"
npm run preview -- --host 0.0.0.0 --port "$FRONTEND_PORT"
popd >/dev/null

kill "$BACKEND_PID" || true


