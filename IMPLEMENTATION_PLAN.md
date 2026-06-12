# Fire & Smoke Detection System — MVP Implementation Plan

**Version:** 1.2 (no Docker — all services run natively; backend is Python FastAPI, not Node.js/Express)
**Date:** 2026-06-11
**Source:** MVP Technical Design Document v1
**Target effort:** 15 working days

---

## 1. Overview

Build an AI-powered fire/smoke detection MVP that:

1. Ingests multiple RTSP camera streams (simulated via MediaMTX during development).
2. Runs a **pretrained YOLO fire/smoke model** (no custom training) on sampled frames.
3. Pushes validated detections to a Python FastAPI backend backed by MongoDB.
4. Displays live camera status, alerts, and incident history on an Angular dashboard.
5. Triggers visual (dashboard red state) and audio alarms on critical events.

```
[Video files] → MediaMTX (RTSP) → Python AI Service (YOLO) → FastAPI Backend → MongoDB
                                                                    │
                                                              Socket.IO (WebSocket)
                                                                    ▼
                                                            Angular Dashboard + Alarm
```

---

## 2. Repository Structure (Monorepo)

```
fire-smoke-detection/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── scripts/
│   ├── start_all.sh            # starts simulator, AI service, backend, dashboard
│   └── stop_all.sh             # stops everything (tracks PIDs in .run/)
│
├── simulator/                  # Camera simulation
│   ├── bin/mediamtx            # standalone MediaMTX binary (single static executable)
│   ├── mediamtx.yml            # MediaMTX config
│   ├── videos/                 # fire.mp4, smoke.mp4, warehouse.mp4, welding.mp4
│   └── start_streams.sh        # launches MediaMTX + ffmpeg loops
│
├── ai-service/                 # Python 3.11+ detection engine
│   ├── requirements.txt
│   ├── config.yaml             # thresholds, camera list, backend URL, FPS
│   ├── models/                 # downloaded pretrained weights (.pt)
│   ├── app/
│   │   ├── main.py             # entrypoint: spawns one worker per camera
│   │   ├── stream_reader.py    # RTSP capture + reconnect logic
│   │   ├── detector.py         # YOLO inference wrapper
│   │   ├── alert_logic.py      # thresholds, debounce, cooldown
│   │   ├── publisher.py        # POST events to backend (with retry queue)
│   │   └── snapshot.py         # annotated frame capture & save
│   └── tests/
│
├── backend/                    # Python FastAPI + MongoDB
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── main.py             # FastAPI app + Socket.IO (ASGI) bootstrap
│   │   ├── config.py           # pydantic-settings (.env loading)
│   │   ├── routers/            # cameras, alerts, incidents, settings
│   │   ├── services/           # alert engine, incident service
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── db/                 # Motor (async MongoDB) client + collections
│   │   ├── sockets/            # Socket.IO event emitters
│   │   └── dependencies.py     # API key auth, shared deps
│   ├── snapshots/              # served statically (/snapshots/*)
│   └── tests/
│
└── dashboard/                  # Angular app
    ├── package.json
    └── src/app/
        ├── core/               # API service, Socket.IO service, models
        ├── features/
        │   ├── monitoring/     # camera grid + live status
        │   ├── alerts/         # active alert panel + alarm audio
        │   └── incidents/      # incident history table + snapshot viewer
        └── shared/             # status badge, confidence bar, etc.
```

### Local Runtime (no Docker)

All services run directly on the host machine:

| Component | How it runs | Install |
|---|---|---|
| MongoDB | systemd service (`mongod`) on `localhost:27017` | MongoDB Community Edition via apt repo (`sudo systemctl enable --now mongod`) |
| MediaMTX | standalone static binary in `simulator/bin/` (no install needed) | download release tarball from GitHub, unpack |
| ffmpeg | host package | `sudo apt install ffmpeg` |
| AI service | Python 3.11 virtualenv → `python -m app.main` | `python3.11 -m venv .venv && pip install -r requirements.txt` |
| Backend | same/another virtualenv → `uvicorn app.main:app --port 8000` | same |
| Dashboard | Angular dev server → `ng serve` (port 4200); production build served by any static server | Node.js LTS (only needed for the Angular toolchain) |

`scripts/start_all.sh` brings up everything in dependency order (checks `mongod` is running → starts MediaMTX + ffmpeg loops → backend → AI service → dashboard), writes PID files to `.run/`, and `stop_all.sh` tears it all down. Each service can also be started individually for development.

---

## 3. Component Design

### 3.1 Camera Simulator (MediaMTX)

- Run **MediaMTX** as a standalone binary (`simulator/bin/mediamtx simulator/mediamtx.yml`), exposing RTSP on `8554`. MediaMTX ships as a single static executable, so no installation or container is needed.
- Loop video files into it with ffmpeg (one process per virtual camera):

  ```bash
  ffmpeg -re -stream_loop -1 -i videos/fire.mp4 -c copy -f rtsp rtsp://localhost:8554/cam1
  ```

- Virtual cameras:

  | Stream | Video | Purpose |
  |---|---|---|
  | `rtsp://localhost:8554/cam1` | fire.mp4 | Positive: fire |
  | `rtsp://localhost:8554/cam2` | smoke.mp4 | Positive: smoke |
  | `rtsp://localhost:8554/cam3` | warehouse.mp4 | Negative: normal ops |
  | `rtsp://localhost:8554/cam4` | welding.mp4 | Negative: false-positive trap |

- `start_streams.sh` launches MediaMTX plus all ffmpeg loops (and stops them); also used by the test suite.

### 3.2 AI Detection Service (Python)

**Model selection (Day 3 spike — pick the best of):**

- Public pretrained YOLOv8 fire/smoke checkpoints (e.g., HuggingFace `keremberke/yolov8m-fire-smoke` family or equivalent Ultralytics community weights).
- Acceptance bar: detects fire in fire.mp4 and smoke in smoke.mp4 at usable confidence, and stays quiet on warehouse.mp4. Welding.mp4 false positives are handled by thresholds + debounce, not the model.
- Keep the model path in `config.yaml` so weights can be swapped without code changes.

**Per-camera worker (process or thread per stream):**

1. Open RTSP with OpenCV (`cv2.VideoCapture` with FFMPEG backend, TCP transport).
2. **Frame sampling:** infer on ~2–4 FPS (configurable), not the full stream rate. Always grab latest frame (drop stale buffered frames) so detections reflect "now".
3. Run YOLO inference (`ultralytics` API), filter to classes `fire` (0) and `smoke` (1).
4. Apply alert logic (below). On a confirmed event: save an annotated snapshot and POST the event to the backend.
5. Send a lightweight **heartbeat** to the backend every ~10 s (camera ONLINE/OFFLINE tracking).

**Alert logic (`alert_logic.py`) — the key false-positive defense:**

- Thresholds (configurable, fetched from backend settings at startup):
  - Fire: confidence > **0.80** → CRITICAL
  - Smoke: confidence > **0.75** → WARNING
- **Debounce:** require N consecutive positive sampled frames (default N=3, ≈1 s) before raising an event. Single-frame flashes (welding sparks, reflections) are discarded.
- **Cooldown:** after raising an event for a camera+type, suppress duplicates for a configurable window (default 60 s) while the condition persists; send a "cleared" state update when M consecutive negative frames occur.
- This is deliberately lightweight — full temporal validation remains Phase 2 as scoped.

**Resilience:**

- RTSP reconnect with exponential backoff (1 s → 30 s cap); mark camera OFFLINE via heartbeat after repeated failures.
- Outbound event POSTs go through a small in-memory retry queue so a backend restart doesn't lose detections.
- Structured logging (camera id, fps, inference latency) for debugging.

**Snapshot handling:** annotated JPEG (bounding boxes + confidence) written to a shared `snapshots/` volume with name `{cameraId}_{timestamp}.jpg`; the event payload carries the filename, and the backend serves the directory statically.

### 3.3 Backend (Python FastAPI + MongoDB)

**Responsibilities:** receive detection events, apply alert-engine rules, persist incidents/alerts, manage cameras, push real-time updates over Socket.IO, serve snapshots.

**Stack:** FastAPI (async) served by Uvicorn, **Motor** for async MongoDB access, **Pydantic** models for request/response validation, **python-socketio** mounted on the same ASGI app (so the Angular `socket.io-client` works unchanged). Auto-generated OpenAPI docs at `/docs` double as the API contract for the dashboard.

A side benefit of dropping Node: the whole server side is now Python, so the AI service and backend share one toolchain, one schema package (the detection-event Pydantic model can be imported by both), and one test runner.

**REST API (`/api/v1`):**

| Method | Path | Purpose |
|---|---|---|
| POST | `/detections` | AI service posts raw detection events (internal, API-key protected) |
| POST | `/cameras/:id/heartbeat` | AI service heartbeat → ONLINE/OFFLINE |
| GET/POST/PUT/DELETE | `/cameras` | Camera CRUD |
| GET | `/alerts` | Active alerts (filter: `status`, `cameraId`) |
| PUT | `/alerts/:id/acknowledge` | Operator acknowledges an alert |
| GET | `/incidents` | Incident history (paginated; filters: camera, type, date range) |
| GET | `/incidents/:id` | Incident detail incl. snapshot URL |
| GET/PUT | `/settings` | Detection thresholds, cooldowns |
| GET | `/health` | Liveness check |

(The design doc's `POST /api/v1/alerts` is realized as `POST /detections` → alert engine → alert created; keeps "raw detection" and "operator-facing alert" cleanly separated.)

**Alert engine (server-side validation, mirrors the doc's rule):**

- `FIRE` with confidence > fire threshold → level **CRITICAL** → create incident + active alert, emit `alert:critical`.
- `SMOKE` with confidence > smoke threshold → level **WARNING** → create incident + active alert, emit `alert:warning`.
- Deduplicate: one active alert per camera+type; repeated events update `lastSeenAt`/max confidence instead of creating new alerts.

**Socket.IO events to dashboard:**

- `camera:status` — online/offline + current detection state per camera
- `alert:new`, `alert:updated`, `alert:cleared`
- `incident:created`

**MongoDB collections & indexes:**

```js
// cameras
{ cameraId, name, location, streamUrl, status: "ONLINE"|"OFFLINE",
  lastHeartbeat, currentState: { fire: bool, smoke: bool, confidence, lastEventAt } }
// index: { cameraId: 1 } unique

// incidents
{ incidentId, cameraId, type: "FIRE"|"SMOKE", level: "CRITICAL"|"WARNING",
  confidence, snapshot, timestamp, acknowledged: bool }
// indexes: { timestamp: -1 }, { cameraId: 1, timestamp: -1 }

// alerts
{ alertId, cameraId, type, level, status: "ACTIVE"|"ACKNOWLEDGED"|"CLEARED",
  firstSeenAt, lastSeenAt, maxConfidence, incidentId }
// index: { status: 1, cameraId: 1 }

// systemlogs
{ level, source, message, timestamp }   // capped collection

// settings (single doc)
{ fireThreshold: 0.80, smokeThreshold: 0.75, debounceFrames: 3, cooldownSeconds: 60 }
```

**Cross-cutting:** request validation via Pydantic schemas (automatic 422s), centralized exception handlers, CORS middleware for the dashboard origin, simple API-key header dependency for the AI-service endpoints, `.env` config via pydantic-settings, structured logging (structlog or stdlib logging with JSON formatter), snapshots served with `StaticFiles`.

### 3.4 Angular Dashboard

**Pages:**

1. **Live Monitoring (main):** card/grid per camera — Camera ID, location, ONLINE/OFFLINE badge, Fire Yes/No, Smoke Yes/No, confidence, last event time. Card turns **red** on CRITICAL, **amber** on WARNING. Optional live preview via MediaMTX's HLS/WebRTC output (stretch goal — status-only is the MVP bar).
2. **Active Alerts:** list of ACTIVE alerts with acknowledge button.
3. **Incident History:** paginated table (event ID, camera, location, type, confidence, timestamp) with snapshot modal and filters.

**Real-time & alarm behavior:**

- `SocketService` wraps Socket.IO client; state held in lightweight RxJS subjects (or Angular signals).
- On `alert:critical`: page-level red banner, camera card red, **audio alarm loops** until every critical alert is acknowledged.
- Browsers block autoplay audio — require one initial user interaction ("Enable alarm audio" button on load) before the alarm can sound. This is a known browser constraint; bake it into the UX from day one.
- On socket disconnect: show "connection lost" banner and fall back to 10 s REST polling.

---

## 4. Configuration (single source of truth)

| Setting | Default | Where |
|---|---|---|
| Fire confidence threshold | 0.80 | `settings` collection (AI service pulls at startup; PUT /settings hot-reloads) |
| Smoke confidence threshold | 0.75 | same |
| Inference FPS per camera | 3 | `ai-service/config.yaml` |
| Debounce frames | 3 | settings |
| Alert cooldown | 60 s | settings |
| Camera list | — | `cameras` collection (AI service fetches on start) |

---

## 5. Build Order & Timeline (15 working days)

The order is chosen so every stage is independently testable and integration risk surfaces early. **The model spike (Day 3) is the highest-risk item — front-loaded deliberately.**

| Days | Milestone | Deliverable / exit criteria |
|---|---|---|
| **1–2** | **Environment & camera simulator** | MongoDB installed and running as a local service; MediaMTX binary + ffmpeg set up; 4 looping RTSP streams verified playable in VLC; repo scaffolding + start/stop scripts; test videos sourced |
| **3–5** | **AI service** | Day 3: model spike — pretrained weights chosen and validated against fire/smoke videos. Days 4–5: multi-camera workers, frame sampling, debounce/cooldown logic, snapshots, event publisher (logs to console until backend exists), reconnect handling |
| **6–7** | **Backend APIs + alert engine** | All REST endpoints with validation; MongoDB schemas + indexes; alert engine dedup rules; Socket.IO emitting; snapshot static serving; AI service switched from console to real POSTs — **end-to-end detection → DB verified via curl** |
| **8–11** | **Angular dashboard** | Day 8: scaffold, API/socket services, camera grid. Day 9: live status + red/amber states. Day 10: alarm audio + active alerts + acknowledge flow. Day 11: incident history + snapshot modal + polish |
| **12–13** | **Integration & testing** | Full pipeline soak test (all 4 streams, 30+ min); positive/negative test matrix executed; threshold/debounce tuning against welding video; reconnect & restart chaos tests |
| **14** | **Hardening & docs** | README with full setup instructions, .env examples, seed script for cameras; bug fixes |
| **15** | **Buffer / demo prep** | Slack for overruns (model spike and dashboard are the likely culprits); demo run-through |

---

## 6. Testing Strategy

### Unit / component

- **AI service:** alert_logic debounce & cooldown (pure functions — easy to unit test); detector wrapper with a stubbed model.
- **Backend:** alert-engine rules (thresholds, dedup), route validation — pytest with FastAPI's `TestClient`/httpx against mongomock-motor, or a dedicated test database on the local `mongod` that the suite drops on teardown.
- **Dashboard:** alert state service, status-badge rendering.

### End-to-end matrix (Days 12–13)

| # | Scenario | Stream | Expected |
|---|---|---|---|
| P1 | Indoor/warehouse fire | cam1 (fire.mp4) | CRITICAL alert, incident + snapshot saved, dashboard red, alarm sounds |
| P2 | Smoke | cam2 (smoke.mp4) | WARNING alert, incident saved, card amber |
| N1 | Normal warehouse | cam3 | No alert for full video duration |
| N2 | Welding / sparks | cam4 | No alert (tune thresholds + debounce until this passes) |
| N3 | Bright lights / reflections / steam | extra clips if available | No alert |
| R1 | Kill a stream mid-run | any | Camera goes OFFLINE on dashboard ≤ 30 s; recovers on stream restart |
| R2 | Restart backend during detections | cam1 | AI service retries; no events permanently lost |
| R3 | Acknowledge critical alert | cam1 | Alarm stops; alert → ACKNOWLEDGED; history retained |
| S1 | Soak: 4 streams, 30 min | all | No memory growth/crash; inference keeps up at target FPS |

### Success criteria (from design doc, all must pass)

✅ Live RTSP streams processed · real-time fire detection · real-time smoke detection · dashboard auto-updates · correct alert generation · alarm on fire · incidents persisted.

---

## 7. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Pretrained model quality is poor (misses fire or fires on welding) | High — core of the product | Day-3 spike with explicit acceptance bar; try 2–3 candidate checkpoints; debounce + thresholds as a second line of defense; thresholds hot-configurable for demo tuning |
| Welding/steam false positives can't be fully eliminated without training | Medium | Document as known MVP limitation (custom training is Phase 2); tune per-camera thresholds if needed |
| RTSP/OpenCV instability (frame corruption, hangs) | Medium | TCP transport, read timeouts, watchdog that recreates the capture, reconnect backoff |
| CPU-only inference too slow for 4 streams | Medium | Use the small/nano model variant; lower sampling FPS; reduce inference resolution (e.g., 640→480); GPU if available |
| Browser blocks alarm audio autoplay | Low but demo-killing | "Enable audio" interaction on dashboard load; visual alarm never depends on audio |
| Multi-service integration friction (Python services + Angular) | Medium (reduced vs. Node — one server-side language) | Contract-first: freeze the detection-event Pydantic schema on Day 3 and share it between AI service and backend; OpenAPI `/docs` as the dashboard contract; e2e smoke test from Day 7 onward |

---

## 8. Explicitly Out of Scope (per design doc)

Custom model training · fire-spread prediction · SMS/WhatsApp/email alerts · edge deployment · mobile app · video analytics reporting. The architecture leaves room for Phase 2 (notification channels plug into the backend alert engine; temporal validation slots into `alert_logic.py`).

---

## 9. Definition of Done

- After the documented one-time setup (MongoDB service, Python venvs, MediaMTX binary, ffmpeg), a single `scripts/start_all.sh` brings up the entire system; `stop_all.sh` shuts it down cleanly.
- All success criteria in §6 pass, demonstrated with the four simulated cameras.
- README covers setup, configuration, adding a real RTSP camera, and the test matrix results.
- No secrets in the repo; `.env.example` provided for backend, `config.yaml` documented for AI service.
