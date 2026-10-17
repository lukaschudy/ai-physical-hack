"""Gemini Flash: 10 batch images -> structured frame-by-frame text."""

from typing import Protocol

from .models import BatchAnnotation, FrameAnnotation


class Annotator(Protocol):
    def annotate(self, images: list[bytes], task: str, batch_start_s: float) -> BatchAnnotation: ...


class FakeAnnotator:
    def annotate(self, images: list[bytes], task: str, batch_start_s: float) -> BatchAnnotation:
        frames = [
            FrameAnnotation(
                index=i,
                timestamp_s=batch_start_s + i,
                action=f"working on: {task}",
                hands="both hands on the object",
                objects=["object"],
                scene="table indoors",
            )
            for i in range(len(images))
        ]
        return BatchAnnotation(frames=frames, summary=f"Contributor continues to {task}.")


class GeminiAnnotator:
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def annotate(self, images: list[bytes], task: str, batch_start_s: float) -> BatchAnnotation:
        raise NotImplementedError
