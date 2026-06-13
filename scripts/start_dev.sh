#!/usr/bin/env bash
# Dev-mode launcher: opens each service in its own terminal window (so you can
# watch live logs / Ctrl-C individually) and opens the dashboard in the
# default browser once it's ready.
#
#   simulator   -> MediaMTX + ffmpeg loops (RTSP :8554)
#   backend     -> FastAPI + Socket.IO (:8000)
#   ai-service  -> YOLO detection workers (one per camera)
#   dashboard   -> Angular dev server (:4200), opened in the browser via `ng serve --open`
#
# For a headless/background variant (logs to .run/logs/, no terminal windows),
# use scripts/start_all.sh / scripts/stop_all.sh instead.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log()  { echo "[start_dev] $*"; }
warn() { echo "[start_dev] WARN: $*" >&2; }

# 1. MongoDB: either a local mongod, or a remote URI configured in backend/.env
#    (MONGO_HOSTS). Only warn for the local case — we can't reach a remote
#    replica set from here to check it.
if pgrep -x mongod >/dev/null; then
    log "mongod is running"
elif grep -q '^MONGO_HOSTS=.*localhost' "$ROOT/backend/.env" 2>/dev/null; then
    warn "mongod is not running locally. Start it with: sudo systemctl start mongod"
else
    log "no local mongod found — assuming backend/.env points at a remote MongoDB"
fi

# Opens a terminal window running the given command (kept open with `exec bash`
# afterwards so you can see errors / re-run things). Falls back to a background
# process if no supported terminal emulator is found.
open_terminal() { # title, command
    local title="$1" cmd="$2"
    if command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal --title="$title" -- bash -c "$cmd; exec bash"
    elif command -v konsole >/dev/null 2>&1; then
        konsole --new-tab -p tabtitle="$title" -e bash -c "$cmd; exec bash" &
    elif command -v xfce4-terminal >/dev/null 2>&1; then
        xfce4-terminal --title="$title" -e "bash -c '$cmd; exec bash'" &
    elif command -v terminator >/dev/null 2>&1; then
        terminator --new-tab -T "$title" -e "bash -c '$cmd; exec bash'" &
    elif command -v xterm >/dev/null 2>&1; then
        xterm -T "$title" -e bash -c "$cmd; exec bash" &
    else
        warn "no supported terminal emulator found — running '$title' in the background (log: .run/logs/dev-$title.log)"
        mkdir -p "$ROOT/.run/logs"
        bash -c "$cmd" > "$ROOT/.run/logs/dev-$title.log" 2>&1 &
    fi
}

log "starting camera simulator..."
if [[ -x "$ROOT/simulator/bin/mediamtx" ]]; then
    open_terminal "Simulator" "cd '$ROOT/simulator' && ./start_streams.sh"
    sleep 2
else
    warn "simulator/bin/mediamtx not found — skipping simulator"
fi

log "starting backend (FastAPI :8000)..."
open_terminal "Backend" "cd '$ROOT/backend' && uv run uvicorn app.main:app --port 8000"
sleep 2

log "starting AI service..."
open_terminal "AI Service" "cd '$ROOT/ai-service' && uv run python -m app.main"
sleep 1

log "starting dashboard (Angular :4200) — will open in your default browser..."
open_terminal "Dashboard" "cd '$ROOT/dashboard' && npx ng serve --port 4200 --open"

log "done — each service is running in its own terminal window."
log "stop each one with Ctrl-C in its window, or close the windows."
