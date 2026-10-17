"""Jev: compare a batch's live annotations with the task references and session context."""

import json
from typing import Any, Protocol

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from .models import Assessment, BatchAnnotation, FrameAnnotation, Session


class Comparer(Protocol):
    def assess(self, session: Session, annotation: BatchAnnotation) -> Assessment: ...


class JevError(RuntimeError):
    """The comparison call failed or returned something unusable."""


class FakeComparer:
    """Deterministic: flags every third batch so the demo exercises the question flow."""

    def assess(self, session: Session, annotation: BatchAnnotation) -> Assessment:
        if len(session.batches) % 3 == 2:
            return Assessment(suspicious=True, reason="Fake: periodic check-in.", confidence=0.6)
        return Assessment(suspicious=False, reason="Consistent with the task.", confidence=0.1)


SYSTEM_INSTRUCTION = """\
You are Jev, a fraud checker for contributors who record themselves doing physical tasks.
Every 10 seconds you get a frame-by-frame text annotation of the newest 10 images, plus the
declared task, labelled reference examples (legit and fraud, with their signals), summaries of
earlier batches, and earlier follow-up questions with the contributor's spoken answers.

Decide whether the newest batch is suspicious, i.e. a follow-up question is warranted.
- Suspicious: it matches a fraud reference's signals (screen replay, static or repeated frames,
  cuts, no contributor hands, someone else doing the work), the scene changes without
  explanation, or the activity stays unrelated to the declared task.
- Not suspicious: normal pauses, setup, fetching or arranging materials, adjusting the camera,
  brief off-task moments, or imperfect technique. Be calibrated: a false alarm interrupts an
  honest contributor, so flag only what a careful reviewer would ask about.
- If the contributor already explained an issue satisfactorily, do not flag it again unless
  the newest batch adds new evidence. An evasive or contradicted answer keeps it open.
- When something is unclear but not clearly fraud, prefer suspicious=true with moderate
  confidence so the contributor is asked to clarify, rather than a high-confidence alarm.

Return JSON: suspicious, reason (one short sentence a human reviewer can read, citing what you
saw), confidence (0-1, how likely something is wrong; low when not suspicious)."""


def _frame_line(f: FrameAnnotation) -> str:
    parts = [f"[{f.index}] t={f.timestamp_s:.1f}s {f.action}"]
    if f.hands:
        parts.append(f"hands: {f.hands}")
    if f.objects:
        parts.append(f"objects: {', '.join(f.objects)}")
    if f.scene:
        parts.append(f"scene: {f.scene}")
    if f.anomalies:
        parts.append(f"anomalies: {', '.join(f.anomalies)}")
    return " | ".join(parts)


def build_prompt(session: Session, annotation: BatchAnnotation) -> str:
    """Everything Jev needs for one batch, as plain text. `session.batches` are earlier batches."""
    refs = [
        f"- [{r.label}] {r.description}"
        + (f" Signals: {'; '.join(r.signals)}." if r.signals else "")
        for r in session.references
    ] or ["- (no references for this task)"]
    history = [
        f"- Batch {b.index} (t={b.started_at_s:.0f}s): {b.annotation.summary}"
        + (f" FLAGGED: {b.assessment.reason}" if b.assessment.suspicious else "")
        for b in session.batches
    ] or ["- (this is the first batch)"]
    answers = {a.question_id: a.transcript for a in session.answers}
    qa = [
        f'- After batch {b.index}, asked: "{b.question.text}" '
        + (f'Answer: "{answers[b.question.id]}"' if b.question.id in answers else "No answer yet.")
        for b in session.batches
        if b.question
    ] or ["- (none)"]
    current = [_frame_line(f) for f in annotation.frames]
    return "\n".join(
        [
            f"Declared task: {session.task}",
            "",
            "Reference examples:",
            *refs,
            "",
            "Earlier batches:",
            *history,
            "",
            "Follow-up questions and answers:",
            *qa,
            "",
            f"Newest batch (index {len(session.batches)}), summary: {annotation.summary}",
            *current,
        ]
    )


class JevOutput(BaseModel):
    """What the model fills in. `checked` stays ours: only failures mark a batch unchecked."""

    suspicious: bool
    reason: str
    confidence: float


def parse_assessment(text: str | None) -> Assessment:
    """Validate the model's JSON; clamp confidence so a slightly-off number doesn't fail a batch."""
    try:
        data: Any = json.loads(text or "")
        if isinstance(data, dict) and isinstance(data.get("confidence"), int | float):
            data["confidence"] = min(1.0, max(0.0, float(data["confidence"])))
        return Assessment(**JevOutput.model_validate(data).model_dump())
    except (json.JSONDecodeError, ValidationError) as e:
        raise JevError(f"Jev returned an invalid assessment: {text!r}") from e


class GeminiComparer:
    def __init__(self, api_key: str, model: str, client: genai.Client | None = None):
        self.api_key, self.model = api_key, model
        self.client = client or genai.Client(api_key=api_key)

    def assess(self, session: Session, annotation: BatchAnnotation) -> Assessment:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=build_prompt(session, annotation),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=JevOutput,
                    # Low thinking keeps latency well under the 10 s batch cadence.
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
        except Exception as e:
            raise JevError(f"Jev comparison call to {self.model} failed: {e}") from e
        return parse_assessment(response.text)
