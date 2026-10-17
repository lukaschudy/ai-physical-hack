"""Session verdict: deterministic heuristic, Gemini judge with an injected client."""

from types import SimpleNamespace

import pytest

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
from app.verdict import (
    EMPTY_SESSION_SCORE,
    FakeJudge,
    GeminiJudge,
    collect_evidence,
    decide,
    heuristic_score,
    is_evasive,
    session_prompt,
)


def batch(index: int, suspicious: bool = False, confidence: float = 0.1, asked: bool = False):
    frame = FrameAnnotation(
        index=0, timestamp_s=index * 10.0, action="folding", scene="kitchen", anomalies=["glare"]
    )
    return Batch(
        index=index,
        started_at_s=index * 10.0,
        image_paths=[],
        annotation=BatchAnnotation(frames=[frame], summary=f"summary {index}"),
        assessment=Assessment(
            suspicious=suspicious,
            reason="screen bezel visible" if suspicious else "consistent",
            confidence=confidence,
        ),
        question=Question(text=f"What is at {index * 10}s?", batch_index=index) if asked else None,
    )


def session(*batches: Batch, answers: dict[int, str] | None = None) -> Session:
    s = Session(
        task="fold a t-shirt",
        references=[
            ReferenceAnnotation(
                id="r1", task="fold a t-shirt", label="fraud", description="screen replay"
            )
        ],
        batches=list(batches),
    )
    for i, text in (answers or {}).items():
        q = s.batches[i].question
        assert q is not None
        s.answers.append(Answer(question_id=q.id, transcript=text))
    return s


GOOD = "I tilted the phone to show the shirt on the table, those are my hands."


class FakeClient:
    def __init__(self, text: str | None = None, error: Exception | None = None):
        self.text, self.error, self.calls = text, error, []
        self.models = self

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def test_decide_thresholds():
    assert [decide(s) for s in (0, 29, 30, 69, 70, 100)] == [
        "accept",
        "accept",
        "review",
        "review",
        "reject",
        "reject",
    ]


@pytest.mark.parametrize(
    ("text", "evasive"),
    [("I don't know", True), ("no comment", True), ("yes", True), (GOOD, False)],
)
def test_is_evasive(text, evasive):
    assert is_evasive(text) is evasive


def test_heuristic_clean_session_accepts():
    v = FakeJudge().verdict(session(batch(0), batch(1), batch(2)))
    assert v.fraud_score == 0 and v.decision == "accept" and v.evidence == []


def test_heuristic_empty_session_goes_to_review():
    v = FakeJudge().verdict(session())
    assert v.fraud_score == EMPTY_SESSION_SCORE and v.decision == "review"


def test_heuristic_answer_quality_orders_scores():
    def score(answer: str | None) -> int:
        b = [batch(0), batch(1, suspicious=True, confidence=0.6, asked=True), batch(2)]
        return heuristic_score(session(*b, answers={1: answer} if answer else None))

    good, evasive, unanswered = score(GOOD), score("I don't know"), score(None)
    assert good < evasive < unanswered
    assert decide(unanswered) == "review"


def test_heuristic_repeated_strong_flags_reject():
    b = [batch(i, suspicious=True, confidence=0.9, asked=True) for i in range(3)]
    v = FakeJudge().verdict(session(*b))
    assert v.fraud_score == 100 and v.decision == "reject" and len(v.evidence) == 3


def test_prompt_contains_whole_session():
    s = session(batch(0), batch(1, suspicious=True, confidence=0.7, asked=True))
    prompt = session_prompt(s)
    for part in ("fold a t-shirt", "[fraud] screen replay", "summary 1", "FLAGGED", "glare"):
        assert part in prompt
    assert "What is at 10s?" in prompt and "UNANSWERED" in prompt


def test_gemini_judge_uses_model_score_and_deterministic_evidence():
    s = session(batch(0), batch(1, suspicious=True, confidence=0.6, asked=True), answers={1: GOOD})
    client = FakeClient('{"fraud_score": 75, "summary": "Screen replay at 10s. Check footage."}')
    v = GeminiJudge("key", "gemini-test", client=client).verdict(s)

    assert v.fraud_score == 75 and v.decision == "reject"
    assert v.summary == "Screen replay at 10s. Check footage."
    assert v.evidence == collect_evidence(s)
    call = client.calls[0]
    assert call["model"] == "gemini-test"
    assert call["contents"] == session_prompt(s)
    assert call["config"].response_mime_type == "application/json"
    assert "UNANSWERED follow-up raises" in call["config"].system_instruction


@pytest.mark.parametrize(
    "client",
    [
        FakeClient(error=RuntimeError("503")),
        FakeClient("not json"),
        FakeClient('{"fraud_score": 140, "summary": "x"}'),
        FakeClient('{"fraud_score": 10, "summary": "  "}'),
        FakeClient(None),
    ],
)
def test_gemini_judge_falls_back_to_heuristic(client):
    s = session(batch(0), batch(1, suspicious=True, confidence=0.6, asked=True))
    v = GeminiJudge("key", "gemini-test", client=client).verdict(s)
    assert v.fraud_score == heuristic_score(s)
    assert v.decision == decide(v.fraud_score)
    assert v.summary.startswith("Automatic fallback")
    assert v.evidence == collect_evidence(s)
