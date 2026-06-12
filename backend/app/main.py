"""FastAPI app + Socket.IO (ASGI) bootstrap (plan §3.3): mounts routers
under /api/v1, the python-socketio server on the same ASGI app, snapshot
StaticFiles at /snapshots, CORS for the dashboard origin, and centralized
exception handlers.

Run with: uvicorn app.main:app --port 8000
"""
