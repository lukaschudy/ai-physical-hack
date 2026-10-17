from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from elevenlabs import ElevenLabs
from elevenlabs.core.api_error import ApiError

from app.stt import ElevenLabsTranscriber, clean_transcript, upload_file


class FakeSTT:
    def __init__(self, text: str | None = "", error: ApiError | None = None):
        self.text, self.error = text, error
        self.calls: list[dict[str, Any]] = []

    def convert(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def transcriber(stt: FakeSTT, model: str = "scribe_v2") -> ElevenLabsTranscriber:
    return ElevenLabsTranscriber("key", model, client=SimpleNamespace(speech_to_text=stt))


@pytest.mark.parametrize(
    ("mime", "name", "ctype"),
    [
        ("audio/webm;codecs=opus", "answer.webm", "audio/webm"),
        ("audio/webm", "answer.webm", "audio/webm"),
        ("audio/mp4", "answer.mp4", "audio/mp4"),
        ("Audio/MP4; codecs=mp4a.40.2", "answer.mp4", "audio/mp4"),
        ("audio/ogg;codecs=opus", "answer.ogg", "audio/ogg"),
        ("application/octet-stream", "answer.webm", "audio/webm"),
        ("", "answer.webm", "audio/webm"),
    ],
)
def test_upload_file(mime: str, name: str, ctype: str) -> None:
    assert upload_file(b"x", mime) == (name, b"x", ctype)


def test_clean_transcript() -> None:
    assert clean_transcript("  I am\n peeling   potatoes. ") == "I am peeling potatoes."
    assert clean_transcript(None) == ""


def test_transcribe_sends_model_and_file() -> None:
    stt = FakeSTT(" Peeling potatoes for dinner. ")
    assert transcriber(stt).transcribe(b"opus", "audio/webm;codecs=opus") == (
        "Peeling potatoes for dinner."
    )
    [call] = stt.calls
    assert call["model_id"] == "scribe_v2"
    assert call["file"] == ("answer.webm", b"opus", "audio/webm")
    assert call["tag_audio_events"] is False


def test_empty_model_falls_back_to_default() -> None:
    stt = FakeSTT("ok")
    transcriber(stt, model="").transcribe(b"a", "audio/mp4")
    assert stt.calls[0]["model_id"] == "scribe_v2"


def test_empty_audio_skips_api() -> None:
    stt = FakeSTT("never")
    assert transcriber(stt).transcribe(b"", "audio/webm") == ""
    assert stt.calls == []


@pytest.mark.parametrize("text", ["", "   ", None])
def test_silent_audio_returns_empty(text: str | None) -> None:
    assert transcriber(FakeSTT(text)).transcribe(b"silence", "audio/webm") == ""


@pytest.mark.parametrize("status", [400, 422])
def test_rejected_audio_returns_empty(status: int) -> None:
    stt = FakeSTT(error=ApiError(status_code=status, body={"detail": "audio too short"}))
    assert transcriber(stt).transcribe(b"x", "audio/webm") == ""


def test_other_api_errors_raise() -> None:
    stt = FakeSTT(error=ApiError(status_code=401, body={"detail": "invalid api key"}))
    with pytest.raises(ApiError):
        transcriber(stt).transcribe(b"x", "audio/webm")


def test_real_sdk_request_shape() -> None:
    """Real SDK over a mocked transport: endpoint, auth header, multipart file + fields."""
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = {"language_code": "en", "language_probability": 0.99, "text": " Hi. ", "words": []}
        return httpx.Response(200, json=body)

    client = ElevenLabs(
        api_key="k", httpx_client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    t = ElevenLabsTranscriber("k", "scribe_v2", client=client)
    assert t.transcribe(b"MP4DATA", "audio/mp4") == "Hi."
    [req] = seen
    body = req.read()
    assert req.url.path == "/v1/speech-to-text" and req.headers["xi-api-key"] == "k"
    assert b'filename="answer.mp4"' in body and b"Content-Type: audio/mp4" in body
    assert b"MP4DATA" in body and b"scribe_v2" in body


def test_real_sdk_bad_request_returns_empty() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(400, json={"detail": "too short"}))
    client = ElevenLabs(api_key="k", httpx_client=httpx.Client(transport=transport))
    assert ElevenLabsTranscriber("k", "", client=client).transcribe(b"x", "audio/webm") == ""
