# Phone Camera Feed via MediaMTX — Implementation Plan (Option 2)

**Goal:** Let a mobile phone act as a live camera in the Live Monitoring grid. The
phone *pushes* its camera over RTMP into the existing MediaMTX server, which
re-exposes it as RTSP. A dashboard control points a camera's `streamUrl` at that
RTSP path, and the existing AI pipeline (sampling → YOLO → debounce/cooldown →
alerts → Socket.IO → alarm) runs on it unchanged.

```
[Phone: Larix Broadcaster]
        │  RTMP push  rtmp://<server-lan-ip>:1935/phonecam
        ▼
   MediaMTX (simulator/) ──re-exposes──> rtsp://127.0.0.1:8554/phonecam
        ▲                                          │
   (already runs cam1..cam4)                       │ cv2.VideoCapture (TCP)
                                                   ▼
                                          AI Service worker  ──POST detections──> Backend ──Socket.IO──> Dashboard
```

**Why option 2 (RTMP→MediaMTX) over pointing the AI service straight at the phone:**
reuses the RTSP plumbing and reconnect/backoff logic already in
`stream_reader.py`; keeps the phone off the AI service directly; survives the
phone dropping in/out (MediaMTX handles the publisher lifecycle); and works with
any standard mobile RTMP broadcaster app.

**What already works (no change needed):**
- `streamUrl` is hot-swappable end to end. Backend stores it per camera; the AI
  service polls `/cameras` every ~10 s and reconnects via
  `_refresh_stream_urls` → `CameraWorker.set_stream_url` → `StreamReader.set_url`
  (`ai-service/app/main.py:147`, `ai-service/app/stream_reader.py:53`).
- `StreamReader` opens any FFMPEG-readable URL over TCP and reconnects with
  exponential backoff, marking the camera OFFLINE when the phone is gone
  (`ai-service/app/stream_reader.py:64`).
- MediaMTX `paths.all_others` already accepts dynamically published streams
  (`simulator/mediamtx.yml:24`), so a new `phonecam` path needs no path config.

---

## Step 1 — Enable RTMP ingest in MediaMTX

**File:** `simulator/mediamtx.yml`

1. Flip RTMP on and bind its port:
   ```yaml
   rtmp: yes
   rtmpAddress: :1935
   rtmpEncryption: "no"
   ```
   (Replace the current `rtmp: no` at `simulator/mediamtx.yml:16`.)
2. Leave `rtsp: yes` / `rtspTransports: [tcp]` as-is — that is how the published
   phone stream gets re-exposed to the AI service.
3. Keep `paths.all_others:` — the phone publishing to `/phonecam` is accepted
   without an explicit path entry. (Optional hardening in Step 7.)

**Verify:** restart the simulator (`simulator/start_streams.sh`) and confirm the
MediaMTX log shows an RTMP listener on `:1935` alongside RTSP on `:8554`.

---

## Step 2 — Open the LAN so the phone can reach the server

1. The phone and the server must be on the same network (same Wi-Fi / LAN).
2. Find the server's LAN IP (`ip addr` / `hostname -I`), e.g. `192.168.1.42`.
3. Open TCP **1935** in the host firewall (only 1935 is needed for an RTMP push;
   8554 stays local to the AI service):
   ```bash
   sudo ufw allow 1935/tcp   # if ufw is active
   ```
4. `rtmpAddress: :1935` already binds all interfaces, so no extra MediaMTX
   change is required.

**Verify:** from another machine/phone, `nc -vz <server-lan-ip> 1935` (or just
attempt the publish in Step 6) succeeds.

---

## Step 3 — Register a "Phone Camera" so the grid has a slot to bind

Pick **one** approach:

- **A. Dedicated camera (recommended).** Seed a `cam5` / "Phone Camera" so the
  simulator's cam1–cam4 test matrix stays intact. Add it to:
  - the backend `cameras` collection (via the seed/bootstrap path you use for
    cam1–cam4, or `POST /api/v1/cameras`), and
  - the AI service fallback list in `ai-service/config.yaml:27` so it still
    appears when the backend isn't seeded:
    ```yaml
    - cameraId: cam5
      streamUrl: rtsp://localhost:8554/phonecam
    ```
  Its initial `streamUrl` can point at `rtsp://localhost:8554/phonecam` directly —
  it just shows OFFLINE until the phone starts publishing.

- **B. Repurpose an existing camera** by setting its `streamUrl` to the phone
  path at runtime (Step 4 endpoint). Simpler, but you lose that simulator stream
  while the phone is connected.

> Convention used below: phone publishes to MediaMTX path **`phonecam`**, read
> back as **`rtsp://localhost:8554/phonecam`** by the AI service (same host).

---

## Step 4 — Backend: endpoint to set a camera's stream URL

**File:** `backend/app/routers/cameras.py` (mirror the existing `upload_feed`
handler at line 75, which already mutates `streamUrl` and emits a socket update).

1. Add a request schema in `backend/app/schemas/cameras.py`:
   ```python
   class StreamUrlUpdate(BaseModel):
       streamUrl: str
   ```
2. Add the endpoint (dashboard-facing, no API key — consistent with
   `/feed`):
   ```python
   ALLOWED_STREAM_SCHEMES = ("rtsp://", "rtmp://", "http://", "https://")

   @router.post("/{camera_id}/stream", response_model=CameraOut)
   async def set_stream_url(
       camera_id: str,
       body: StreamUrlUpdate,
       db: AsyncIOMotorDatabase = Depends(get_db),
   ) -> dict:
       camera = await db.cameras.find_one({"cameraId": camera_id})
       if camera is None:
           raise HTTPException(status.HTTP_404_NOT_FOUND, "camera not found")
       if not body.streamUrl.startswith(ALLOWED_STREAM_SCHEMES):
           raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported stream URL scheme")
       await db.cameras.update_one(
           {"cameraId": camera_id}, {"$set": {"streamUrl": body.streamUrl}}
       )
       camera = await db.cameras.find_one({"cameraId": camera_id})
       await emit_camera_status(strip_id(camera))
       return strip_id(camera)
   ```
   Reuses `emit_camera_status` so the dashboard reflects the change immediately,
   and the AI service picks it up on its next `_refresh_stream_urls` tick.

> Why not just `PUT /cameras/{id}`? That endpoint exists and accepts `streamUrl`
> (`CameraUpdate`), but it does **not** emit a socket update. A dedicated
> `/stream` endpoint keeps the dashboard live and the intent explicit.

**Tests:** `backend/tests` — add cases for: 200 + persisted `streamUrl` + socket
emit on a valid `rtsp://` URL; 400 on a bad scheme; 404 on unknown camera.

---

## Step 5 — Dashboard: a "Connect phone" control

**Files:** `dashboard/src/app/core/services/api.service.ts`,
`dashboard/src/app/features/monitoring/monitoring.component.ts` + `.html`.

1. API client method (next to `uploadFeed`, `api.service.ts:26`):
   ```typescript
   setStreamUrl(cameraId: string, streamUrl: string): Observable<Camera> {
     return this.http.post<Camera>(
       `${this.baseUrl}/cameras/${cameraId}/stream`, { streamUrl });
   }
   ```
2. In `monitoring.component.ts`, add a `connectPhone(camera)` method that calls
   `setStreamUrl(camera.cameraId, 'rtsp://localhost:8554/phonecam')` and
   `upsertCamera` on success (same pattern as `uploadFeed`,
   `monitoring.component.ts:65`).
3. In `monitoring.component.html`, next to the existing "Upload video feed"
   label, add a **"Use phone feed"** button and a short hint block showing the
   RTMP publish target so the operator knows where to point the phone:
   ```
   Publish from your phone to:
     rtmp://<server-lan-ip>:1935/phonecam
   ```
   (Hardcode/derive the server IP; optionally render a QR of the RTMP URL later
   to make Larix setup one-tap.)

> Keep it minimal: one button to bind the camera to the phone path, plus the
> publish URL shown as instructions. Reverting to the simulator is just setting
> the URL back to `rtsp://localhost:8554/camN` (optionally add a "Reset to
> simulator" button using the same endpoint).

---

## Step 6 — Phone setup (no code)

1. Install a mobile RTMP broadcaster — **Larix Broadcaster** (free, iOS +
   Android) is the reference choice.
2. Add a new connection of type **RTMP** with URL:
   `rtmp://<server-lan-ip>:1935/phonecam`
3. Recommended encoder settings for CPU-only inference: **H.264**, 720p,
   ~2 Mbps, keyframe interval ~2 s. (Detection samples ~3 FPS regardless, so a
   modest bitrate is fine and lighter on the network.)
4. Tap **Go Live / Publish**.

---

## Step 7 — (Optional) Lock down the publish path

`paths.all_others` accepts any publisher, which is fine on a trusted LAN. To
restrict it, replace it in `simulator/mediamtx.yml` with an explicit path that
requires a publish credential:
```yaml
paths:
  phonecam:
    publishUser: phone
    publishPass: <secret>
  all_others:
```
Then the Larix URL becomes
`rtmp://phone:<secret>@<server-lan-ip>:1935/phonecam`.

---

## Step 8 — End-to-end verification

1. Start everything: `scripts/start_all.sh` (MediaMTX + AI service + backend +
   dashboard), or the dev launcher.
2. On the phone, start publishing to `rtmp://<server-lan-ip>:1935/phonecam`.
3. **MediaMTX:** log shows a publisher connected on `phonecam`.
4. **MediaMTX→RTSP sanity (optional):** on the server,
   `ffprobe rtsp://127.0.0.1:8554/phonecam` returns a video stream.
5. **Dashboard:** open Live Monitoring → on the Phone Camera card click
   **Use phone feed**. Within ~10 s (the heartbeat/refresh tick) the card flips
   to **ONLINE**.
6. **Detection:** point the phone at a fire/smoke source (e.g. a phone screen
   playing test footage, or a real controlled flame). Confirm the confidence bar
   rises, an alert appears, and on CRITICAL the alarm fires (once audio is
   enabled).
7. **Resilience:** stop publishing on the phone → the card returns to OFFLINE
   (StreamReader backoff + heartbeat). Resume → it reconnects automatically.

**Success criteria:** a live phone stream produces detections and alerts
identical in behavior to the simulator cameras, and connect/disconnect is handled
without restarting any service.

---

## Files touched (summary)

| File | Change |
| --- | --- |
| `simulator/mediamtx.yml` | Enable `rtmp: yes` + `rtmpAddress: :1935` (Step 1); optional path auth (Step 7) |
| `backend/app/schemas/cameras.py` | Add `StreamUrlUpdate` schema (Step 4) |
| `backend/app/routers/cameras.py` | Add `POST /cameras/{id}/stream` (Step 4) |
| `backend/tests/...` | Tests for the new endpoint (Step 4) |
| `ai-service/config.yaml` | Optional `cam5` fallback entry (Step 3A) |
| `dashboard/.../core/services/api.service.ts` | Add `setStreamUrl` (Step 5) |
| `dashboard/.../features/monitoring/monitoring.component.ts` + `.html` | "Use phone feed" control + publish-URL hint (Step 5) |
| backend camera seed | Add a "Phone Camera" entry (Step 3A) |

**No changes** to `ai-service/app/stream_reader.py` or `main.py` — stream switching
and RTSP reconnect already cover the phone source.

## Out of scope (separate stretch goals)
- **Live video *preview* in the dashboard grid** (browsers can't play RTSP).
  Would require enabling MediaMTX HLS/WebRTC (`hls: yes`) and embedding the
  player — independent of detection, which works regardless.
- Custom-trained weights / model changes — pretrained checkpoint only, per
  `IMPLEMENTATION_PLAN.md`.

## Risks / notes
- **CPU:** the phone is one more worker doing ~3 FPS YOLO on CPU. Fine for one
  extra camera; watch load if combined with all four simulator streams.
- **Same-LAN requirement:** for remote phones you'd need a public/NAT-traversed
  endpoint (port-forward 1935, or a TURN/relay) — out of scope for the MVP.
- **Codec:** publish H.264; MediaMTX re-muxes RTMP→RTSP without transcoding.
