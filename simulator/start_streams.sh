#!/usr/bin/env bash
# Launches MediaMTX plus one looping ffmpeg publisher per virtual camera (plan §3.1):
#   cam1: fire.mp4      (positive: fire)
#   cam2: smoke.mp4     (positive: smoke)
#   cam3: warehouse.mp4 (negative: normal ops)
#   cam4: welding.mp4   (negative: false-positive trap)
# Runs in the foreground; Ctrl-C (or killing the process group) stops everything.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RTSP_BASE="rtsp://localhost:8554"

declare -A CAMERAS=(
    [cam1]=fire.mp4
    [cam2]=smoke.mp4
    [cam3]=warehouse.mp4
    [cam4]=welding.mp4
)

if [[ ! -x "$DIR/bin/mediamtx" ]]; then
    echo "ERROR: $DIR/bin/mediamtx not found." >&2
    echo "Download the release tarball from https://github.com/bluenviron/mediamtx/releases and unpack the binary there." >&2
    exit 1
fi

command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg not installed (sudo apt install ffmpeg)" >&2; exit 1; }

cleanup() { kill 0 2>/dev/null; }
trap cleanup EXIT INT TERM

"$DIR/bin/mediamtx" "$DIR/mediamtx.yml" &
sleep 2  # give the RTSP listener time to come up

for cam in "${!CAMERAS[@]}"; do
    video="$DIR/videos/${CAMERAS[$cam]}"
    if [[ ! -f "$video" ]]; then
        echo "WARN: $video missing — skipping $cam" >&2
        continue
    fi
    ffmpeg -nostdin -loglevel error -re -stream_loop -1 -i "$video" \
        -c copy -f rtsp -rtsp_transport tcp "$RTSP_BASE/$cam" &
    echo "publishing $cam <- ${CAMERAS[$cam]}"
done

wait
