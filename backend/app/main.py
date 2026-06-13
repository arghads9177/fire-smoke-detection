# FastAPI app + Socket.IO (ASGI) bootstrap (plan §3.3): mounts routers
# under /api/v1, the python-socketio server on the same ASGI app, snapshot
# StaticFiles at /snapshots, CORS for the dashboard origin, and centralized
# exception handlers.
#
# Run with: uvicorn app.main:app --port 8000

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import get_settings
from app.routers import alerts, cameras, detections, health, incidents
from app.routers import settings as settings_router
from app.sockets import sio

log = logging.getLogger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database = db.connect()
    await db.init_indexes(database)
    try:
        await db.ensure_capped_systemlogs(database)
    except Exception:
        log.warning("could not create systemlogs collection", exc_info=True)
    yield
    db.disconnect()


settings = get_settings()

fastapi_app = FastAPI(title="Fire & Smoke Detection API", lifespan=lifespan)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@fastapi_app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@fastapi_app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    log.exception("unhandled exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal server error"},
    )


fastapi_app.include_router(health.router, prefix="/api/v1")
fastapi_app.include_router(detections.router, prefix="/api/v1")
fastapi_app.include_router(cameras.router, prefix="/api/v1")
fastapi_app.include_router(alerts.router, prefix="/api/v1")
fastapi_app.include_router(incidents.router, prefix="/api/v1")
fastapi_app.include_router(settings_router.router, prefix="/api/v1")

snapshots_dir = Path(settings.snapshots_dir)
snapshots_dir.mkdir(parents=True, exist_ok=True)
fastapi_app.mount("/snapshots", StaticFiles(directory=snapshots_dir), name="snapshots")

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="socket.io")
