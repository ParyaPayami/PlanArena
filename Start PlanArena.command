#!/bin/zsh
# PlanArena launcher. Double-click to start; your browser opens the Studio.
# "Start PlanArena (phone).command" also makes it reachable from a phone on the same Wi-Fi.
cd "$(dirname "$0")"
PORT=8787
HOST=127.0.0.1
[[ "$1" == "--phone" ]] && HOST=0.0.0.0

if curl -s -m 2 "http://127.0.0.1:$PORT/api/health" | grep -q '"ok":true'; then
  echo "PlanArena is already running."
  open "http://localhost:$PORT"
  exit 0
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "First run: installing Python packages (a few minutes)..."
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || { echo "Install failed."; read; exit 1; }
  echo "$PWD" > "$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')/planarena_repo.pth"
fi

if [[ ! -f data/processed/parcels.parquet ]]; then
  echo "First run: downloading city data and training the models (about an hour)..."
  .venv/bin/python -I -m planarena.twin.fetch \
    && .venv/bin/python -I -m planarena.twin.build \
    && .venv/bin/python -I -m planarena.calibrate \
    && .venv/bin/python -m planarena.models.train \
    || { echo "Setup failed."; read; exit 1; }
  echo "Optional: the redevelopment layer needs older MapPLUTO releases; see README (planarena.models.transition)."
fi

if [[ ! -f web/dist/index.html ]]; then
  echo "Building the web app (needs Node.js)..."
  (cd web && npm install && npx vite build) || { echo "Web build failed."; read; exit 1; }
fi

echo "Starting PlanArena..."
PYTHONWARNINGS=ignore .venv/bin/python -m planarena.api --host "$HOST" --port "$PORT" &
SERVER=$!
trap "kill $SERVER 2>/dev/null" EXIT INT TERM
for i in {1..90}; do
  curl -s -m 1 "http://127.0.0.1:$PORT/api/health" >/dev/null && break
  sleep 1
done
open "http://localhost:$PORT"
echo ""
echo "  Studio (desktop):   http://localhost:$PORT"
echo "  Phone game:         http://localhost:$PORT/play"
if [[ "$HOST" == "0.0.0.0" ]]; then
  IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
  echo "  On your phone (same Wi-Fi): http://$IP:$PORT/play"
  echo "  Note: anyone on this Wi-Fi can open it while it runs. Use a trusted network."
fi
echo ""
echo "Close this window (or press Ctrl-C) to stop PlanArena."
wait $SERVER
