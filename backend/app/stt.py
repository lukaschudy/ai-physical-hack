"""ElevenLabs speech-to-text: transcribe the contributor's spoken answer."""

from typing import Protocol


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, mime: str) -> str: ...


class FakeTranscriber:
    def transcribe(self, audio: bytes, mime: str) -> str:
        return "I am doing the task I declared."


class ElevenLabsTranscriber:
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def transcribe(self, audio: bytes, mime: str) -> str:
        raise NotImplementedError
