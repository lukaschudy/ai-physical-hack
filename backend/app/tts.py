"""ElevenLabs text-to-speech: voice Astra's question in Shift."""

import io
import wave
from typing import Any, Protocol

from elevenlabs.client import ElevenLabs

# 64 kbps MP3 is clear for speech; larger formats add latency without audible gain.
OUTPUT_FORMAT = "mp3_44100_64"


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

    def __init__(self, api_key: str, voice_id: str, model: str, client: Any = None):
        self.api_key, self.voice_id, self.model = api_key, voice_id, model
        self.client = client or ElevenLabs(api_key=api_key)

    def synthesize(self, text: str) -> bytes:
        """The SDK streams the MP3 as chunks; join them into one file."""
        chunks = self.client.text_to_speech.convert(
            self.voice_id, text=text, model_id=self.model, output_format=OUTPUT_FORMAT
        )
        return b"".join(chunks)
