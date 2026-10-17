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


def answer(client, sid, qid, audio=b"fake"):
    return client.post(
        f"/api/sessions/{sid}/answers",
        data={"question_id": qid},
        files={"audio": ("a.webm", audio, "audio/webm")},
    )


def flagged_question(client):
    s = client.post("/api/sessions", json={"task": "fold a t-shirt"}).json()
    for _ in range(3):
        r = client.post(f"/api/sessions/{s['id']}/batches", files=images()).json()
    return s["id"], r["batch"]["question"]["id"]


def test_captured_at(client):
    s = client.post("/api/sessions", json={"task": "fold a t-shirt"}).json()
    url = f"/api/sessions/{s['id']}/batches"
    r = client.post(url, files=images(), data={"captured_at_s": "7.5"})
    assert r.json()["batch"]["started_at_s"] == 7.5
    assert client.post(url, files=images()).json()["batch"]["started_at_s"] == 10
    assert client.post(url, files=images(), data={"captured_at_s": "-1"}).status_code == 422


def test_bad_images(client):
    s = client.post("/api/sessions", json={"task": "fold a t-shirt"}).json()
    url = f"/api/sessions/{s['id']}/batches"
    text = images()[:9] + [("images", ("x.txt", b"hi", "text/plain"))]
    assert client.post(url, files=text).status_code == 415
    empty = images()[:9] + [("images", ("9.jpg", b"", "image/jpeg"))]
    r = client.post(url, files=empty)
    assert r.status_code == 422 and "9.jpg" in r.text
    assert client.get(f"/api/sessions/{s['id']}").json()["batches"] == []


def test_bad_answers(client):
    sid, qid = flagged_question(client)
    assert answer(client, sid, qid, audio=b"").status_code == 422
    assert answer(client, sid, "nope").status_code == 404
    assert answer(client, sid, qid).status_code == 200
    r = answer(client, sid, qid)
    assert r.status_code == 409 and "already answered" in r.text


def test_external_failures_map_to_502(tmp_path, monkeypatch):
    class Down:
        def transcribe(self, audio, mime):
            raise RuntimeError("down")

        def verdict(self, session):
            raise RuntimeError("down")

    monkeypatch.setenv("USE_FAKES", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    pipe = build_pipeline(load_settings())
    pipe.transcriber = pipe.judge = Down()
    client = TestClient(create_app(pipe))
    sid, qid = flagged_question(client)
    assert answer(client, sid, qid).status_code == 502
    assert client.post(f"/api/sessions/{sid}/finish").status_code == 502
    assert client.get(f"/api/sessions/{sid}").json()["status"] == "active"
