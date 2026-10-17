"""scripts/replay.py against a real HTTP server running the offline-fake pipeline."""

import json
import socket
import threading

import pytest
import uvicorn

from app.config import load_settings
from app.deps import build_pipeline
from app.main import create_app
from scripts import replay


@pytest.fixture
def base_url(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_FAKES", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(create_app(build_pipeline(load_settings())), log_level="warning")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    while not server.started:
        thread.join(0.01)
    yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    server.should_exit = True
    thread.join(5)


def write_frames(directory, n):
    directory.mkdir()
    for i in range(n):
        (directory / f"{i:04d}.jpg").write_bytes(b"\xff\xd8fake")
    (directory / "notes.txt").write_text("ignored")
    return directory


def test_frame_batches_sorted_and_drops_remainder(tmp_path):
    frames = write_frames(tmp_path / "f", 23)
    batches, dropped = replay.frame_batches(frames)
    assert [len(b) for b in batches] == [10, 10] and dropped == 3
    assert [p.name for p in batches[1]][:2] == ["0010.jpg", "0011.jpg"]


def test_encode_multipart():
    body, ctype = replay.encode_multipart({"q": "1"}, [("f", "a.jpg", b"\x00\xff", "image/jpeg")])
    boundary = ctype.split("boundary=")[1]
    assert body.startswith(f"--{boundary}\r\n".encode()) and body.endswith(
        f"--{boundary}--\r\n".encode()
    )
    assert b'name="q"\r\n\r\n1\r\n' in body and b'filename="a.jpg"' in body and b"\x00\xff" in body


def test_replay_end_to_end(base_url, tmp_path, capsys):
    frames = write_frames(tmp_path / "f", 35)
    audio = tmp_path / "answer.mp3"
    audio.write_bytes(b"fake audio")

    replay.main(
        [
            "--task",
            "fold a t-shirt",
            str(frames),
            "--answer-audio",
            str(audio),
            "--base-url",
            base_url,
        ]
    )

    out, err = capsys.readouterr()
    verdict = json.loads(out)
    assert verdict["decision"] in {"accept", "review", "reject"}
    assert verdict["evidence"][0]["answer"]  # fake pipeline asks on batch 2; we answered it
    assert "dropping last 5 frame(s)" in err and "Astra:" in err


def test_replay_needs_a_full_batch(base_url, tmp_path):
    with pytest.raises(SystemExit, match="at least 10"):
        replay.main(
            [
                "--task",
                "fold a t-shirt",
                str(write_frames(tmp_path / "f", 4)),
                "--base-url",
                base_url,
            ]
        )
