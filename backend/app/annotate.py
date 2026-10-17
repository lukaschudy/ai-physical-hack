"""Gemini Flash: 10 batch images -> structured frame-by-frame text."""

from typing import Any, Protocol

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

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


class AnnotationError(RuntimeError):
    """Flash returned unusable output twice in a row."""


# What Flash fills in. index/timestamp_s are set by us, not trusted from the model.
class FlashFrame(BaseModel):
    action: str = Field(description="What the contributor is doing in this frame.")
    hands: str = Field(description="Whose hands are visible, their position, what they hold.")
    objects: list[str] = Field(description="Task-relevant objects visible in the frame.")
    scene: str = Field(description="Location and setting: room, surface, lighting, camera view.")
    anomalies: list[str] = Field(description="Fraud signals seen in this frame; empty if none.")


class FlashBatch(BaseModel):
    frames: list[FlashFrame] = Field(description="Exactly one entry per image, in input order.")
    summary: str = Field(description="One or two sentences on the whole 10-second batch.")


SYSTEM_PROMPT = """\
You annotate first-person recordings of contributors performing physical tasks for a \
robotics dataset. Your text is used to detect fraud, so describe only what is visible; \
never guess or fill gaps with what the task implies.

You receive consecutive frames taken 1 second apart, in order. Return exactly one frame \
entry per image, in the same order.

Per frame:
- action: what the contributor is physically doing right now (verb + object), or "none".
- hands: whose hands are visible (contributor's own from the camera's view, or someone \
else's), how many, their position and what they hold. Say "no hands visible" if none.
- objects: task-relevant objects in view.
- scene: location, surface, lighting, camera viewpoint.
- anomalies: list every fraud signal you see, else an empty list. Look for:
  - a screen, monitor, phone or TV showing the activity (replay of a video) - bezels, \
moire patterns, screen glare or reflections, pixel grids, refresh banding, UI overlays
  - frames that are static, frozen, or identical/repeated compared with neighbouring frames
  - scene cuts: sudden changes of location, lighting, viewpoint or objects between frames
  - the contributor's hands missing while the task is apparently progressing
  - another person doing the work instead of the contributor
  - activity unrelated to the declared task, or no activity at all
  - anything else implausible for a live first-person recording

summary: one or two sentences on the whole batch, including whether it matches the \
declared task and any anomalies.
"""


class GeminiAnnotator:
    def __init__(self, api_key: str, model: str, client: Any = None):
        self.model = model
        self.client = client or genai.Client(api_key=api_key)

    def annotate(self, images: list[bytes], task: str, batch_start_s: float) -> BatchAnnotation:
        contents = build_contents(images, task)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_json_schema=FlashBatch.model_json_schema(),
            temperature=0,
        )
        error = ""
        for _ in range(2):  # retry once on bad or partial output
            response = self.client.models.generate_content(
                model=self.model, contents=contents, config=config
            )
            try:
                return parse_batch(response.text, len(images), batch_start_s)
            except ValueError as e:
                error = str(e)
        raise AnnotationError(f"Gemini Flash returned unusable annotations twice: {error}")


def build_contents(images: list[bytes], task: str) -> list[Any]:
    parts: list[Any] = [f"Declared task: {task}\nFrames: {len(images)}, 1 second apart."]
    for i, image in enumerate(images):
        parts += [f"Frame {i} (t={i}s):", types.Part.from_bytes(data=image, mime_type="image/jpeg")]
    return parts


def parse_batch(text: str | None, n_frames: int, batch_start_s: float) -> BatchAnnotation:
    """Validate Flash's JSON and add index/timestamp. Raises ValueError on bad output."""
    if not text:
        raise ValueError("empty response")
    try:
        batch = FlashBatch.model_validate_json(text)
    except ValidationError as e:  # also covers malformed JSON
        raise ValueError(f"invalid JSON: {e.errors()[0]['msg']}") from e
    if len(batch.frames) != n_frames:
        raise ValueError(f"expected {n_frames} frames, got {len(batch.frames)}")
    frames = [
        FrameAnnotation(index=i, timestamp_s=batch_start_s + i, **f.model_dump())
        for i, f in enumerate(batch.frames)
    ]
    return BatchAnnotation(frames=frames, summary=batch.summary)
