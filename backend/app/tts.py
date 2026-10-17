"""ElevenLabs text-to-speech: voice Astra's question in Shift."""

import io
import wave
from typing import Protocol


class Speaker(Protocol):
    mime: str

    def synthesize(self, text: str) -> bytes: ...


class FakeSpeaker:
    mime = "audio/wav"

    def synthesize(self, text: str) -> bytes:
        """Half a second of silence."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\0\0" * 8000)
        return buf.getvalue()


class ElevenLabsSpeaker:
    mime = "audio/mpeg"

    def __init__(self, api_key: str, voice_id: str, model: str):
        self.api_key, self.voice_id, self.model = api_key, voice_id, model

    def synthesize(self, text: str) -> bytes:
        raise NotImplementedError
