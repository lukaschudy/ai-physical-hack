"""ElevenLabs speech-to-text: transcribe the contributor's spoken answer."""

import logging
from typing import Any, Protocol

from elevenlabs import ElevenLabs
from elevenlabs.core.api_error import ApiError

log = logging.getLogger(__name__)

# MediaRecorder output: audio/webm (Opus) from Chrome/Firefox, audio/mp4 from Safari.
AUDIO_EXT = {
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
}


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, mime: str) -> str: ...


class FakeTranscriber:
    def transcribe(self, audio: bytes, mime: str) -> str:
        return "I am doing the task I declared."


def upload_file(audio: bytes, mime: str) -> tuple[str, bytes, str]:
    """(filename, bytes, content type) for the upload. Drops codec params; unknown -> webm."""
    base = mime.split(";")[0].strip().lower()
    if base not in AUDIO_EXT:
        base = "audio/webm"  # Chrome's default; a missing Blob type arrives as octet-stream
    return f"answer.{AUDIO_EXT[base]}", audio, base


def clean_transcript(text: str | None) -> str:
    return " ".join((text or "").split())


class ElevenLabsTranscriber:
    def __init__(self, api_key: str, model: str, client: Any = None):
        self.api_key, self.model = api_key, model or "scribe_v2"
        self.client = client or ElevenLabs(api_key=api_key)

    def transcribe(self, audio: bytes, mime: str) -> str:
        if not audio:
            return ""
        try:
            result = self.client.speech_to_text.convert(
                model_id=self.model,
                file=upload_file(audio, mime),
                tag_audio_events=False,  # no "(laughter)"-style tags in the transcript
            )
        except ApiError as e:
            # Too-short or undecodable recordings come back as 400/422: treat as no answer.
            if e.status_code in (400, 422):
                log.warning("ElevenLabs STT rejected audio (%s): %s", e.status_code, e.body)
                return ""
            raise
        return clean_transcript(getattr(result, "text", None))
