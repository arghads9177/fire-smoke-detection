# Make `app` importable when pytest runs from the repo root (uv run pytest),
# and provide a TestClient wired to an in-memory mongomock database so tests
# never touch the real MongoDB replica set in .env.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app import db
from app.main import app, fastapi_app

API_KEY = "changeme"  # matches backend/.env API_KEY (app.config defaults to this too)


@pytest.fixture
def mock_db():
    client = AsyncMongoMockClient()
    return client["test"]


@pytest.fixture
def client(mock_db):
    async def _get_db():
        return mock_db

    fastapi_app.dependency_overrides[db.get_db] = _get_db
    yield TestClient(app)
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": API_KEY}
