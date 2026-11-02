"""Pytest fixtures: swap production dependencies (Postgres, storage) for test doubles.

- SQLite in-memory via StaticPool (all connections share one ephemeral DB)
- dependency_overrides replaces get_db/get_storage — the DI seams from the app
- TestClient calls the full ASGI app in-process: no sockets, no uvicorn
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  registers all tables on Base.metadata
from app.core.db import Base, get_db
from app.main import app
from app.services.storage import FilesystemStorage, get_storage

# StaticPool: one shared connection — otherwise each connect() gets a
# DIFFERENT empty in-memory DB and tables "disappear" between calls.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(tmp_path):
    """FastAPI TestClient wired to ephemeral SQLite + tmp-dir storage."""
    Base.metadata.create_all(engine)
    storage = FilesystemStorage(str(tmp_path / "uploads"))

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


@pytest.fixture
def auth_headers(client):
    """Register a user and return Authorization headers."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "motdepasse123"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
