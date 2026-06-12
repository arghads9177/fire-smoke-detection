# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This is an AI-powered fire/smoke detection MVP at the **scaffolding stage** — almost no code exists yet. `IMPLEMENTATION_PLAN.md` is the authoritative spec (architecture, API contract, build order, test matrix). Read it before implementing any component, and keep new code consistent with it.

## Environment & Commands

Python is managed with **uv** (`.venv` already created; Python 3.11+ required, currently 3.12).

```bash
uv add <package>          # add a dependency (updates pyproject.toml + uv.lock)
uv run <script.py>        # run inside the project venv
uv run pytest             # run tests
uv run pytest path/to/test_file.py::test_name   # run a single test
```

Once services exist (per the plan): `scripts/start_all.sh` / `scripts/stop_all.sh` bring the whole system up/down; no Docker — everything runs natively (MongoDB via systemd, MediaMTX as a standalone binary in `simulator/bin/`).

## Architecture (planned monorepo)

```
[Video files] → MediaMTX (RTSP) → Python AI Service (YOLO) → FastAPI Backend → MongoDB
                                                                   │
                                                             Socket.IO (WebSocket)
                                                                   ▼
                                                           Angular Dashboard + Alarm
```

Four components, each independently startable:

- **`simulator/`** — MediaMTX RTSP server on port 8554 + ffmpeg loops feeding 4 virtual cameras (fire, smoke, normal warehouse, welding false-positive trap).
- **`ai-service/`** — one worker per camera: OpenCV RTSP capture (TCP, reconnect with backoff), YOLO inference via `ultralytics` on sampled frames (~3 FPS), then alert logic (debounce N=3 consecutive frames, 60 s cooldown) before POSTing events. Pretrained weights only — no custom training (out of scope).
- **`backend/`** — FastAPI + Motor (async MongoDB) + python-socketio on one ASGI app, port 8000. Receives detections at `POST /api/v1/detections` (API-key protected), runs the alert engine (fire conf > 0.80 → CRITICAL, smoke > 0.75 → WARNING, dedup: one active alert per camera+type), persists to MongoDB, emits Socket.IO events to the dashboard, serves snapshots statically.
- **`dashboard/`** — Angular (port 4200): live camera grid, active alerts with acknowledge, incident history. Audio alarm loops on CRITICAL until acknowledged (requires an "enable audio" user interaction first — browser autoplay constraint).

## Key Design Decisions

- **Shared schema:** the detection-event Pydantic model is shared between ai-service and backend — change it in one place, never fork it.
- **Config lives in two places by design:** runtime-tunable thresholds (fire/smoke confidence, debounce, cooldown) live in the MongoDB `settings` collection and are hot-reloadable via `PUT /settings`; static config (camera list source, FPS, model path) lives in `ai-service/config.yaml`. Model weights path stays in config so checkpoints can be swapped without code changes.
- **False-positive defense is layered:** thresholds + debounce + cooldown in `alert_logic.py`, not the model. The welding stream (cam4) is the negative test that must pass.
- **Raw detections vs. operator alerts are separate concepts:** the AI service POSTs detections; the backend's alert engine decides whether that becomes/updates an alert and incident.

## Testing

- Backend: pytest with FastAPI `TestClient`/httpx against mongomock-motor (or a disposable test DB on local mongod).
- AI service: alert_logic debounce/cooldown are pure functions — unit test them directly; stub the model for detector tests.
- The end-to-end scenario matrix and success criteria are in IMPLEMENTATION_PLAN.md §6.
