"""Session stores (memory + SQLite) and BlobStore path safety."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app.models import Session, Verdict
from app.store import BlobStore, MemorySessionStore, SqliteSessionStore

T0 = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    return (
        MemorySessionStore()
        if request.param == "memory"
        else SqliteSessionStore(tmp_path / "app.db")
    )


def test_save_get_roundtrip(store):
    s = Session(task="fold a t-shirt", created_at=T0)
    store.save(s)
    assert store.get(s.id) == s
    assert store.get("missing") is None


def test_save_overwrites(store):
    s = Session(task="fold a t-shirt", created_at=T0)
    store.save(s)
    s.status = "finished"
    s.verdict = Verdict(fraud_score=10, decision="accept", summary="fine")
    store.save(s)
    got = store.get(s.id)
    assert got is not None and got.status == "finished" and got.verdict == s.verdict
    assert len(store.list()) == 1


def test_returns_copies(store):
    s = Session(task="fold a t-shirt", created_at=T0)
    store.save(s)
    store.get(s.id).status = "finished"  # type: ignore[union-attr]
    store.list()[0].status = "finished"
    assert store.get(s.id).status == "active"  # type: ignore[union-attr]


def test_list_newest_first(store):
    sessions = [Session(task=f"task {i}", created_at=T0 + timedelta(seconds=i)) for i in range(3)]
    for s in [sessions[1], sessions[0], sessions[2]]:
        store.save(s)
    assert [s.id for s in store.list()] == [s.id for s in reversed(sessions)]


def test_sqlite_survives_restart(tmp_path):
    db = tmp_path / "nested" / "dir" / "app.db"  # parent dirs created on demand
    s = Session(task="fold a t-shirt", created_at=T0)
    SqliteSessionStore(db).save(s)
    reopened = SqliteSessionStore(db)
    assert reopened.get(s.id) == s
    assert reopened.list() == [s]


def test_sqlite_concurrent_saves(tmp_path):
    store = SqliteSessionStore(tmp_path / "app.db")
    sessions = [Session(task=f"task {i}") for i in range(50)]
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(store.save, sessions))
        got = list(pool.map(lambda s: store.get(s.id), sessions))
    assert got == sessions
    assert len(store.list()) == 50


def test_blob_put_and_path(tmp_path):
    blobs = BlobStore(tmp_path)
    rel = blobs.put("sessions/abc/batch_000/00.jpg", b"img")
    assert rel == "sessions/abc/batch_000/00.jpg"
    assert blobs.path(rel).read_bytes() == b"img"


@pytest.mark.parametrize(
    "rel", ["../outside.txt", "a/../../outside.txt", "/etc/passwd", "sessions/../../x"]
)
def test_blob_rejects_traversal(tmp_path, rel):
    blobs = BlobStore(tmp_path / "data")
    with pytest.raises(ValueError):
        blobs.path(rel)
    with pytest.raises(ValueError):
        blobs.put(rel, b"evil")
    assert not (tmp_path / "outside.txt").exists()


def test_blob_rejects_symlink_escape(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (tmp_path / "secret").mkdir()
    (root / "link").symlink_to(tmp_path / "secret")
    blobs = BlobStore(root)
    with pytest.raises(ValueError):
        blobs.path("link/x.txt")
    with pytest.raises(ValueError):
        blobs.put("link/x.txt", b"evil")
    assert not (tmp_path / "secret" / "x.txt").exists()


def test_app_sessions_survive_restart(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import load_settings
    from app.deps import build_pipeline
    from app.main import create_app

    monkeypatch.setenv("USE_FAKES", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "fresh"))  # created on startup
    first = TestClient(create_app(build_pipeline(load_settings())))
    s = first.post("/api/sessions", json={"task": "fold a t-shirt"}).json()
    second = TestClient(create_app(build_pipeline(load_settings())))
    assert second.get(f"/api/sessions/{s['id']}").json() == s
    assert (tmp_path / "fresh" / "app.db").is_file()
