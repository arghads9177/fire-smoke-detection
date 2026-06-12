#!/usr/bin/env bash
# Stops every service started by start_all.sh, using PID files in .run/.
# Kills each process group so child processes (ffmpeg loops, etc.) die too.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"

if [[ ! -d "$RUN_DIR" ]]; then
    echo "[stop_all] nothing to stop (.run/ does not exist)"
    exit 0
fi

shopt -s nullglob
for pidfile in "$RUN_DIR"/*.pid; do
    name="$(basename "$pidfile" .pid)"
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
        # negative pid targets the whole process group
        kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null
        echo "[stop_all] stopped $name (pid $pid)"
    else
        echo "[stop_all] $name (pid $pid) was not running"
    fi
    rm -f "$pidfile"
done

# ffmpeg loops are spawned by start_streams.sh; sweep any survivors pushing to our RTSP port
pkill -f "rtsp://localhost:8554" 2>/dev/null && echo "[stop_all] swept leftover ffmpeg streams"

echo "[stop_all] done"
