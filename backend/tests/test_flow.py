"""End-to-end session flow with offline fakes."""

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.deps import build_pipeline
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_FAKES", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(create_app(build_pipeline(load_settings())))


def images(n=10):
    return [("images", (f"{i}.jpg", b"\xff\xd8fake", "image/jpeg")) for i in range(n)]


def test_full_session(client):
    s = client.post("/api/sessions", json={"task": "fold a t-shirt"}).json()
    assert s["status"] == "active" and s["references"]

    results = [
        client.post(f"/api/sessions/{s['id']}/batches", files=images()).json() for _ in range(3)
    ]
    assert [r["question_audio_url"] is not None for r in results] == [False, False, True]
    q = results[2]["batch"]["question"]

    audio = client.get(results[2]["question_audio_url"])
    assert audio.status_code == 200 and audio.content

    a = client.post(
        f"/api/sessions/{s['id']}/answers",
        data={"question_id": q["id"]},
        files={"audio": ("a.webm", b"fake", "audio/webm")},
    ).json()
    assert a["answer"]["transcript"]

    done = client.post(f"/api/sessions/{s['id']}/finish").json()
    v = done["verdict"]
    assert done["status"] == "finished"
    assert v["decision"] in {"accept", "review", "reject"}
    assert v["evidence"][0]["question"] == q["text"]
    assert v["evidence"][0]["answer"] == a["answer"]["transcript"]

    img = client.get(f"/api/files/{done['batches'][0]['image_paths'][0]}")
    assert img.status_code == 200

    assert client.post(f"/api/sessions/{s['id']}/batches", files=images()).status_code == 409


def test_wrong_batch_size(client):
    s = client.post("/api/sessions", json={"task": "fold a t-shirt"}).json()
    assert client.post(f"/api/sessions/{s['id']}/batches", files=images(3)).status_code == 422


def test_unknown_session(client):
    assert client.post("/api/sessions/nope/finish").status_code == 404


def test_file_path_traversal(client):
    assert client.get("/api/files/..%2F..%2Fetc%2Fpasswd").status_code in {400, 404}
