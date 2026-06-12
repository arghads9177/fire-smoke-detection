# Dashboard (Angular)

Not scaffolded yet — generate it in place on Day 8 (plan §5) with the Angular CLI:

```bash
ng new dashboard --directory . --routing --style scss
```

Planned structure (plan §2):

```
src/app/
├── core/        # API service, Socket.IO service, models
├── features/
│   ├── monitoring/   # camera grid + live status (red on CRITICAL, amber on WARNING)
│   ├── alerts/       # active alert panel + alarm audio (needs "enable audio" interaction)
│   └── incidents/    # incident history table + snapshot viewer
└── shared/      # status badge, confidence bar, etc.
```

Dev server: `ng serve` (port 4200), talking to the backend at `http://localhost:8000/api/v1`
and Socket.IO on the same origin. On socket disconnect: "connection lost" banner + 10 s REST polling.
