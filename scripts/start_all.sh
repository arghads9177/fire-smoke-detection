#!/usr/bin/env bash
# Starts the full system in dependency order:
#   mongod check -> simulator (MediaMTX + ffmpeg) -> backend -> AI service -> dashboard
# PID files are written to .run/ so stop_all.sh can tear everything down.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$RUN_DIR" "$LOG_DIR"

log()  { echo "[start_all] $*"; }
warn() { echo "[start_all] WARN: $*" >&2; }

start_bg() { # name, command...
    local name="$1"; shift
    if [[ -f "$RUN_DIR/$name.pid" ]] && kill -0 "$(cat "$RUN_DIR/$name.pid")" 2>/dev/null; then
        log "$name already running (pid $(cat "$RUN_DIR/$name.pid")) — skipping"
        return
    fi
    "$@" >"$LOG_DIR/$name.log" 2>&1 &
    echo $! > "$RUN_DIR/$name.pid"
    log "started $name (pid $!, log: .run/logs/$name.log)"
}

# 1. MongoDB must already be running as a system service
if ! pgrep -x mongod >/dev/null; then
    echo "[start_all] ERROR: mongod is not running. Start it with: sudo systemctl start mongod" >&2
    exit 1
fi
log "mongod is running"

# 2. Camera simulator (MediaMTX + ffmpeg loops)
if [[ -x "$ROOT/simulator/bin/mediamtx" ]]; then
    start_bg simulator "$ROOT/simulator/start_streams.sh"
else
    warn "simulator/bin/mediamtx not found — skipping simulator (see simulator/README in plan §3.1)"
fi

# 3. Backend (FastAPI on :8000)
if [[ -f "$ROOT/backend/app/main.py" && -s "$ROOT/backend/app/main.py" ]]; then
    start_bg backend bash -c "cd '$ROOT/backend' && uv run uvicorn app.main:app --port 8000"
else
    warn "backend not implemented yet — skipping"
fi

# 4. AI detection service
if [[ -f "$ROOT/ai-service/app/main.py" && -s "$ROOT/ai-service/app/main.py" ]]; then
    start_bg ai-service bash -c "cd '$ROOT/ai-service' && uv run python -m app.main"
else
    warn "ai-service not implemented yet — skipping"
fi

# 5. Dashboard (Angular dev server on :4200)
if [[ -f "$ROOT/dashboard/package.json" ]]; then
    start_bg dashboard bash -c "cd '$ROOT/dashboard' && npx ng serve --port 4200"
else
    warn "dashboard not scaffolded yet — skipping"
fi

log "done. Stop everything with scripts/stop_all.sh"
