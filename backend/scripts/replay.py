"""Replay a directory of JPEG frames through a running backend, without a camera or browser.

Stdlib only. Frames are sent in sorted filename order, 10 per batch; an incomplete last batch is
dropped. When Astra asks a question, the --answer-audio file (if given) is posted as the spoken
answer. The verdict JSON is printed to stdout; progress goes to stderr.

Usage (from backend/, with the API running on --base-url):
    uv run python scripts/replay.py --task "fold a t-shirt" frames/
    uv run python scripts/replay.py --task "fold a t-shirt" frames/ \\
        --answer-audio answer.mp3 --base-url http://localhost:8000

Frames can be cut from a video at 1 frame/s, e.g.:
    ffmpeg -i clip.mp4 -vf fps=1 -q:v 3 frames/%04d.jpg
"""

import argparse
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

BATCH_SIZE = 10
JPEG_SUFFIXES = {".jpg", ".jpeg"}

Part = tuple[str, str, bytes, str]  # field name, filename, content, content type


def encode_multipart(fields: dict[str, str], files: list[Part]) -> tuple[bytes, str]:
    """Build a multipart/form-data body; returns (body, content type header)."""
    boundary = uuid4().hex
    out = bytearray()
    for name, value in fields.items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        out += f"{value}\r\n".encode()
    for name, filename, content, ctype in files:
        out += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode()
        out += content + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def frame_batches(directory: Path, size: int = BATCH_SIZE) -> tuple[list[list[Path]], int]:
    """Sorted JPEGs in full batches of `size`, plus the count of dropped trailing frames."""
    frames = sorted(p for p in directory.iterdir() if p.suffix.lower() in JPEG_SUFFIXES)
    full = len(frames) - len(frames) % size
    return [frames[i : i + size] for i in range(0, full, size)], len(frames) - full


class Client:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, body: bytes | None = None, ctype: str | None = None) -> dict:
        req = urllib.request.Request(self.base_url + path, data=body, method="POST")
        if ctype:
            req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req) as res:
                return json.load(res)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"POST {path} -> {e.code}: {e.read().decode(errors='replace')}") from e
        except urllib.error.URLError as e:
            raise SystemExit(f"cannot reach {self.base_url}: {e.reason}") from e

    def create_session(self, task: str) -> dict:
        return self.request(
            "/api/sessions", json.dumps({"task": task}).encode(), "application/json"
        )

    def post_batch(self, session_id: str, frames: list[Path]) -> dict:
        parts = [("images", f.name, f.read_bytes(), "image/jpeg") for f in frames]
        body, ctype = encode_multipart({}, parts)
        return self.request(f"/api/sessions/{session_id}/batches", body, ctype)

    def post_answer(self, session_id: str, question_id: str, audio: Path) -> dict:
        mime = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
        body, ctype = encode_multipart(
            {"question_id": question_id}, [("audio", audio.name, audio.read_bytes(), mime)]
        )
        return self.request(f"/api/sessions/{session_id}/answers", body, ctype)

    def finish(self, session_id: str) -> dict:
        return self.request(f"/api/sessions/{session_id}/finish")


def replay(client: Client, task: str, frames_dir: Path, answer_audio: Path | None) -> dict:
    """Run one session end to end; returns the finished session."""
    batches, dropped = frame_batches(frames_dir)
    if not batches:
        raise SystemExit(f"need at least {BATCH_SIZE} JPEGs in {frames_dir}")
    if dropped:
        log(f"dropping last {dropped} frame(s): incomplete batch")
    session = client.create_session(task)
    log(f"session {session['id']}: {len(batches)} batch(es)")
    for frames in batches:
        batch = client.post_batch(session["id"], frames)["batch"]
        a = batch["assessment"]
        log(f"batch {batch['index']}: {'SUSPICIOUS' if a['suspicious'] else 'ok'} - {a['reason']}")
        if q := batch["question"]:
            log(f"  Astra: {q['text']}")
            if answer_audio:
                answer = client.post_answer(session["id"], q["id"], answer_audio)["answer"]
                log(f"  answer: {answer['transcript']}")
            else:
                log("  (unanswered: no --answer-audio)")
    return client.finish(session["id"])


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("frames_dir", type=Path, help="directory of JPEG frames (1 per second)")
    p.add_argument("--task", required=True, help="declared task, e.g. 'fold a t-shirt'")
    p.add_argument("--answer-audio", type=Path, help="audio file posted as every spoken answer")
    p.add_argument("--base-url", default="http://localhost:8000")
    args = p.parse_args(argv)
    if not args.frames_dir.is_dir():
        p.error(f"not a directory: {args.frames_dir}")
    if args.answer_audio and not args.answer_audio.is_file():
        p.error(f"not a file: {args.answer_audio}")
    session = replay(Client(args.base_url), args.task, args.frames_dir, args.answer_audio)
    print(json.dumps(session["verdict"], indent=2))


if __name__ == "__main__":
    main()
