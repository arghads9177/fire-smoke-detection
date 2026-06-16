# Fire & Smoke Detection System

An AI-powered, real-time fire and smoke detection system for multi-camera surveillance environments. It ingests RTSP streams, runs a pretrained YOLOv8 model on live frames, and surfaces alerts on a live Angular dashboard with audio alarms — no cloud dependency, no Docker.

```
[RTSP Cameras / Simulator] → AI Service (YOLOv8) → FastAPI Backend → MongoDB
                                                           │
                                                     Socket.IO (WebSocket)
                                                           ▼
                                                  Angular Dashboard + Audio Alarm
```

---

## Features

- **Real-time detection** — YOLOv8 fire/smoke inference at ~3 FPS per stream, with sub-second alert latency
- **False-positive defense** — layered: per-class confidence thresholds + N-frame debounce + per-camera cooldown window
- **Live dashboard** — camera grid with ONLINE/OFFLINE badges, CRITICAL (red) / WARNING (amber) states, active alert panel, paginated incident history with annotated snapshot viewer
- **Audio alarm** — loops on CRITICAL until every active alert is acknowledged (browser autoplay-safe)
- **Phone camera support** — stream any phone camera via WebRTC/WHEP for sub-100 ms preview latency
- **Video upload** — upload a local video file as a camera feed for testing
- **Socket.IO real-time updates** — dashboard auto-updates without polling; falls back to 10 s REST polling on disconnect
- **Hot-reloadable thresholds** — fire/smoke confidence, debounce frames, and cooldown seconds adjustable live via `PUT /api/v1/settings` without restarting anything
- **Incident history** — every detection event persisted to MongoDB with annotated JPEG snapshot

---

## Architecture

| Component | Stack | Port |
|---|---|---|
| **Camera Simulator** | MediaMTX (static binary) + ffmpeg | 8554 (RTSP) |
| **AI Service** | Python 3.12, OpenCV, Ultralytics YOLOv8 | — (worker processes) |
| **Backend** | Python FastAPI, Motor, python-socketio, MongoDB | 8000 |
| **Dashboard** | Angular 17+ | 4200 |

All services run **natively on the host** — no Docker required.

---

## Prerequisites

| Dependency | Install |
|---|---|
| Python 3.11+ | system package or pyenv |
| [uv](https://github.com/astral-sh/uv) | `pip install uv` or `curl -Ls https://astral.sh/uv/install.sh \| sh` |
| MongoDB Community Edition | [MongoDB install docs](https://www.mongodb.com/docs/manual/installation/) — must run as a local `mongod` service |
| ffmpeg | `sudo apt install ffmpeg` |
| Node.js LTS | [nodejs.org](https://nodejs.org/) — only needed for the Angular dashboard |
| MediaMTX binary | Download the latest release from [bluenviron/mediamtx](https://github.com/bluenviron/mediamtx/releases) and place it at `simulator/bin/mediamtx` |

---

## Setup

### 1. Clone and prepare the Python environment

```bash
git clone https://github.com/arghads9177/fire-smoke-detection.git
cd fire-smoke-detection
uv sync
```

### 2. Download the YOLO model weights

```bash
# Pretrained YOLOv8n fire/smoke checkpoint (CPU-friendly, ~6 MB)
# Source: https://huggingface.co/rabahdev/fire-smoke-yolov8n
mkdir -p ai-service/models
# Download rabahdev-fire-smoke-yolov8n.pt into ai-service/models/
```

### 3. Configure the backend

```bash
cp backend/.env.example backend/.env
# Edit backend/.env:
#   MONGO_HOSTS=localhost:27017   (for a local unauthenticated mongod)
#   MONGO_DB=fire_smoke_detection
#   API_KEY=your-secret-key       (must match ai-service/config.yaml)
#   CORS_ORIGIN=http://localhost:4200
```

### 4. Configure the AI service

`ai-service/config.yaml` holds the model path, inference FPS, backend URL, and API key. The camera list is fetched from MongoDB at startup; the entries in `config.yaml` serve as a fallback if the backend is unreachable.

```yaml
backend:
  url: http://localhost:8000/api/v1
  api_key: your-secret-key   # must match backend .env API_KEY
```

### 5. Install dashboard dependencies

```bash
cd dashboard && npm install && cd ..
```

### 6. Add test videos (optional — for the simulator)

Place four looping video files in `simulator/videos/`:

| File | Camera | Purpose |
|---|---|---|
| `fire.mp4` | cam1 | Positive: fire |
| `smoke.mp4` | cam2 | Positive: smoke |
| `warehouse.mp4` | cam3 | Negative: normal operations |
| `welding.mp4` | cam4 | Negative: false-positive trap |

---

## Running

### Full stack (recommended)

```bash
# Ensure mongod is running first
sudo systemctl start mongod

scripts/start_all.sh   # starts simulator → backend → AI service → dashboard
scripts/stop_all.sh    # stops everything
```

Logs are written to `.run/logs/`. Each service can also be started individually for development:

```bash
# Simulator only
simulator/start_streams.sh

# Backend only
cd backend && uv run uvicorn app.main:app --port 8000 --reload

# AI service only
cd ai-service && uv run python -m app.main

# Dashboard only
cd dashboard && npx ng serve --port 4200
```

### Development shortcut

```bash
scripts/start_dev.sh   # backend + AI service with auto-reload; no simulator or dashboard
```

---

## Dashboard

Open **http://localhost:4200** in a browser.

- **Live Monitoring** — camera grid with live status. Click *Enable alarm audio* once on first load so the browser permits the alarm sound.
- **Active Alerts** — lists all ACTIVE alerts; *Acknowledge* stops the alarm for that alert.
- **Incident History** — paginated table with snapshot modal and camera/type/date filters.

Interactive API documentation (OpenAPI/Swagger) is available at **http://localhost:8000/docs**.

---

## Connecting a Real RTSP Camera

Add the camera via the REST API:

```bash
curl -X POST http://localhost:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "cameraId": "cam6",
    "name": "Warehouse East",
    "location": "Building A",
    "streamUrl": "rtsp://192.168.1.100:554/stream"
  }'
```

The AI service discovers cameras from MongoDB on startup. Restart it (or it picks up changes on next poll) to start processing the new stream.

### Phone camera (WebRTC/WHEP)

Any phone can act as a live camera with sub-100 ms latency:

1. Open the MediaMTX WHEP publish endpoint on your phone's browser.
2. Add a camera entry with `streamUrl: rtsp://localhost:8554/phonecam/live`.

---

## Configuration Reference

| Setting | Default | Where |
|---|---|---|
| Fire confidence threshold | 0.80 → CRITICAL | MongoDB `settings` collection |
| Smoke confidence threshold | 0.75 → WARNING | MongoDB `settings` collection |
| Debounce frames | 3 (~1 s) | MongoDB `settings` collection |
| Alert cooldown | 60 s | MongoDB `settings` collection |
| Inference FPS per camera | 3 | `ai-service/config.yaml` |
| Model weights path | `models/rabahdev-fire-smoke-yolov8n.pt` | `ai-service/config.yaml` |

Thresholds, debounce, and cooldown are hot-reloadable — no restart needed:

```bash
curl -X PUT http://localhost:8000/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"fireThreshold": 0.85, "smokeThreshold": 0.75, "debounceFrames": 3, "cooldownSeconds": 60}'
```

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/detections` | API key | AI service posts raw detection events |
| `POST` | `/api/v1/cameras/:id/heartbeat` | API key | Camera online/offline heartbeat |
| `GET/POST/PUT/DELETE` | `/api/v1/cameras` | — | Camera CRUD |
| `GET` | `/api/v1/alerts` | — | Active alerts (filter: status, cameraId) |
| `PUT` | `/api/v1/alerts/:id/acknowledge` | — | Acknowledge an alert |
| `GET` | `/api/v1/incidents` | — | Incident history (paginated; filter: camera, type, date) |
| `GET` | `/api/v1/incidents/:id` | — | Incident detail with snapshot URL |
| `GET/PUT` | `/api/v1/settings` | — | Detection thresholds and cooldown |
| `GET` | `/api/v1/health` | — | Liveness check |

Annotated snapshot images are served statically at `/snapshots/{filename}`.

---

## Testing

```bash
# Backend unit + integration tests (uses mongomock-motor)
cd backend && uv run pytest

# AI service alert-logic unit tests (pure functions — no model or RTSP needed)
cd ai-service && uv run pytest
```

### End-to-end test matrix

| # | Scenario | Stream | Expected outcome |
|---|---|---|---|
| P1 | Fire | cam1 (fire.mp4) | CRITICAL alert, snapshot saved, dashboard red, alarm sounds |
| P2 | Smoke | cam2 (smoke.mp4) | WARNING alert, snapshot saved, dashboard amber |
| N1 | Normal warehouse | cam3 (warehouse.mp4) | No alert for full video duration |
| N2 | Welding / sparks | cam4 (welding.mp4) | No alert (threshold + debounce filters sparks) |
| R1 | Kill a stream mid-run | any | Camera → OFFLINE on dashboard within 30 s; recovers on stream restart |
| R2 | Restart backend during detection | cam1 | AI service retries; no events lost |
| R3 | Acknowledge critical alert | cam1 | Alarm stops; alert → ACKNOWLEDGED; history retained |
| S1 | Soak: 4 streams, 30 min | all | No memory growth or crash; inference keeps up at target FPS |

---

## Model

The system uses **[rabahdev/fire-smoke-yolov8n](https://huggingface.co/rabahdev/fire-smoke-yolov8n)** — a YOLOv8n checkpoint pretrained on fire and smoke images. It runs comfortably at 3 FPS per stream on CPU-only hardware. The model path is externalized in `config.yaml` so any compatible checkpoint can be dropped in without code changes.

False-positive suppression (welding sparks, reflections, steam) is handled entirely by the threshold + debounce + cooldown pipeline in `ai-service/app/alert_logic.py`. Custom model training is out of scope for this version.

---

## Out of Scope

Custom model training · fire-spread prediction · email/SMS/push notifications · edge deployment · mobile app · video analytics reporting.

---

## License

MIT
