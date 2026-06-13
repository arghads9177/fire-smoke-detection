# Motor (async MongoDB) client + collection handles and index creation
# (plan §3.3 collections: cameras, incidents, alerts, systemlogs, settings).

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

log = logging.getLogger("db")

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def connect() -> AsyncIOMotorDatabase:
    """Create the Motor client from settings and cache the database handle."""
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db]
    return _db


def disconnect() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency; overridden in tests with a mongomock database."""
    if _db is None:
        raise RuntimeError("database not connected — call db.connect() on startup")
    return _db


async def init_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create indexes idempotently (plan §3.3)."""
    await db.cameras.create_index("cameraId", unique=True)
    await db.incidents.create_index("incidentId", unique=True)
    await db.incidents.create_index([("timestamp", -1)])
    await db.incidents.create_index([("cameraId", 1), ("timestamp", -1)])
    await db.alerts.create_index("alertId", unique=True)
    await db.alerts.create_index([("status", 1), ("cameraId", 1)])


async def ensure_capped_systemlogs(db: AsyncIOMotorDatabase, size_bytes: int = 1_000_000) -> None:
    """Create the `systemlogs` capped collection if it doesn't exist yet."""
    existing = await db.list_collection_names()
    if "systemlogs" not in existing:
        await db.create_collection("systemlogs", capped=True, size=size_bytes)


def strip_id(doc: dict) -> dict:
    """Drop MongoDB's `_id` before returning a document over the API/sockets."""
    doc.pop("_id", None)
    return doc
