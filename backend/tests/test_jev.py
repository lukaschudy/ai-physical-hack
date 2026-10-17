"""Jev per-batch comparison: prompt construction and the Gemini client with the SDK mocked."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.jev import SYSTEM_INSTRUCTION, GeminiComparer, JevError, build_prompt, parse_assessment
from app.models import (
    Answer,
    Assessment,
    Batch,
    BatchAnnotation,
    FrameAnnotation,
    Question,
    ReferenceAnnotation,
    Session,
)


def annotation(
    summary: str = "Folds the left sleeve.", anomalies: tuple[str, ...] = ()
) -> BatchAnnotation:
    frames = [
        FrameAnnotation(
            index=i,
            timestamp_s=20 + i,
            action="folding sleeve",
            hands="left hand on sleeve",
            objects=["t-shirt"],
            scene="kitchen table",
            anomalies=list(anomalies),
        )
        for i in range(10)
    ]
    return BatchAnnotation(frames=frames, summary=summary)


def batch(index: int, summary: str, flagged: str = "", question: str = "") -> Batch:
    return Batch(
        index=index,
        started_at_s=index * 10.0,
        image_paths=[],
        annotation=annotation(summary),
        assessment=Assessment(suspicious=bool(flagged), reason=flagged or "ok", confidence=0.5),
        question=Question(id=f"q{index}", text=question, batch_index=index) if question else None,
    )


def session() -> Session:
    return Session(
        task="fold a t-shirt",
        references=[
            ReferenceAnnotation(
                id="l", task="fold a t-shirt", label="legit", description="Folds on a table."
            ),
            ReferenceAnnotation(
                id="f",
                task="fold a t-shirt",
                label="fraud",
                description="Phone replays a folding video.",
                signals=["screen replay", "no contributor hands"],
            ),
        ],
        batches=[
            batch(0, "Lays the shirt flat."),
            batch(1, "Scene switches to a bedroom.", "Scene changed.", "Why did the room change?"),
            batch(2, "Hands off-screen.", "No hands visible.", "Where are your hands?"),
        ],
        answers=[Answer(question_id="q1", transcript="I moved to better light.")],
    )


def test_prompt_contains_task_references_history_and_qa():
    prompt = build_prompt(session(), annotation(anomalies=("screen bezel",)))
    assert "Declared task: fold a t-shirt" in prompt
    assert "- [legit] Folds on a table." in prompt
    assert (
        "[fraud] Phone replays a folding video. Signals: screen replay; no contributor hands."
        in (prompt)
    )
    assert "- Batch 0 (t=0s): Lays the shirt flat." in prompt
    assert "Batch 1 (t=10s): Scene switches to a bedroom. FLAGGED: Scene changed." in prompt
    assert 'asked: "Why did the room change?" Answer: "I moved to better light."' in prompt
    assert 'asked: "Where are your hands?" No answer yet.' in prompt
    assert "Newest batch (index 3), summary: Folds the left sleeve." in prompt
    assert (
        "[0] t=20.0s folding sleeve | hands: left hand on sleeve | objects: t-shirt"
        " | scene: kitchen table | anomalies: screen bezel" in prompt
    )
    # Earlier batches come before the newest one.
    assert prompt.index("Earlier batches:") < prompt.index("Newest batch")


def test_prompt_for_first_batch_without_references():
    prompt = build_prompt(Session(task="water plants"), annotation())
    assert "(no references for this task)" in prompt
    assert "(this is the first batch)" in prompt
    assert "Follow-up questions and answers:\n- (none)" in prompt
    assert "Newest batch (index 0)" in prompt
    assert "anomalies" not in prompt


def test_system_instruction_is_calibrated():
    text = SYSTEM_INSTRUCTION.lower()
    assert "normal pauses" in text and "explained" in text and "clarify" in text


class FakeModels:
    def __init__(self, text: str | None = None, error: Exception | None = None):
        self.text, self.error, self.calls = text, error, []

    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def comparer(models: FakeModels) -> GeminiComparer:
    return GeminiComparer("key", "gemini-test", client=SimpleNamespace(models=models))  # type: ignore[arg-type]


def test_assess_calls_gemini_with_structured_output():
    models = FakeModels(
        '{"suspicious": true, "reason": "Screen bezel visible.", "confidence": 0.8}'
    )
    s, a = session(), annotation()
    result = comparer(models).assess(s, a)
    assert result == Assessment(suspicious=True, reason="Screen bezel visible.", confidence=0.8)
    call = models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["contents"] == build_prompt(s, a)
    assert call["config"].system_instruction == SYSTEM_INSTRUCTION
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_schema is Assessment


def test_assess_wraps_api_errors():
    models = FakeModels(error=RuntimeError("503 unavailable"))
    with pytest.raises(JevError, match="gemini-test failed: 503 unavailable") as e:
        comparer(models).assess(session(), annotation())
    assert isinstance(e.value.__cause__, RuntimeError)


@pytest.mark.parametrize("text", [None, "", "not json", '{"suspicious": true}', "[]"])
def test_assess_rejects_invalid_output(text):
    with pytest.raises(JevError, match="invalid assessment"):
        comparer(FakeModels(text)).assess(session(), annotation())


def test_parse_assessment_clamps_confidence():
    assert (
        parse_assessment('{"suspicious": false, "reason": "ok", "confidence": 1.3}').confidence == 1
    )
    assert (
        parse_assessment('{"suspicious": false, "reason": "ok", "confidence": -2}').confidence == 0
    )
