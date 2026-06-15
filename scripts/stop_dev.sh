#!/usr/bin/env bash
# Stops the services started by start_dev.sh (terminal-window dev mode).
# Each service is found by matching its command line and killed directly;
# the "exec bash" shell left behind in each terminal window is unaffected,
# so the windows stay open.
set -uo pipefail

patterns=(
    "simulator/bin/mediamtx"
    "ffmpeg .*rtsp://127.0.0.1:8554"
    "uv run uvicorn app.main:app --port 8000"
    "uv run python -m app.main"
    "ng serve --port 4200"
    "esbuild --service="
)

any=0
for pattern in "${patterns[@]}"; do
    if pkill -f "$pattern" 2>/dev/null; then
        echo "[stop_dev] stopped processes matching: $pattern"
        any=1
    fi
done

if [[ "$any" -eq 0 ]]; then
    echo "[stop_dev] nothing to stop"
else
    echo "[stop_dev] done"
fi
