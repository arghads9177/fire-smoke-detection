# Dashboard (Angular)

Angular 19 standalone app, scaffolded per plan §2/§3.4/§5 (Day 8).

```
src/app/
├── core/
│   ├── models/      # Camera, Alert, Incident, DetectionSettings (mirror backend schemas)
│   └── services/     # ApiService (HTTP), SocketService (Socket.IO + RxJS subjects)
├── layout/
│   └── nav/          # top navigation
├── features/
│   ├── monitoring/   # camera grid + live status (red on CRITICAL, amber on WARNING)
│   ├── alerts/        # active alert panel + acknowledge flow
│   └── incidents/     # incident history table + snapshot modal + filters
└── shared/
    └── components/    # status-badge, confidence-bar
```

## Configuration

`src/environments/environment.development.ts` points at the backend on
`http://localhost:8000`; `environment.ts` (production) assumes the dashboard
is served from the same origin as the backend (relative `/api/v1`, `/`, snapshots).

## Development server

```bash
ng serve
```

Open `http://localhost:4200/`. The backend (`uvicorn app.main:app --port 8000`) must
be running for the API and Socket.IO connections to succeed.

## Still TODO (plan §5, Days 9–11)

- Audio alarm + "enable audio" interaction, alarm loop on CRITICAL until acknowledged
- 10 s REST polling fallback when the socket is disconnected
- Camera card live preview (stretch goal)
