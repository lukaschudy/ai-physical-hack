"""Live smoke tests: one real client per test, called through its Protocol.

Skipped unless USE_FAKES=0 and the service's API key is set (env or backend/.env).
Run only these: `uv run pytest -m live`; skip them: `uv run pytest -m "not live"`.
"""

import base64
from dataclasses import replace

import pytest

from app.annotate import FakeAnnotator
from app.config import load_settings
from app.deps import build_pipeline
from app.models import Answer, Assessment, Batch, BatchAnnotation, Question, Session
from app.pipeline import Pipeline

SETTINGS = load_settings()
TASK = "fold a t-shirt"

# 32x32 grayscale baseline JPEG: dark square on a light background (169 bytes).
JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABALDA4MChAODQ4SERATGCgaGBYWGDEjJR0oOjM9PDkzODdASFxOQERX"
    "RTc4UG1RV19iZ2hnPk1xeXBkeFxlZ2P/wAALCAAgACABAREA/8QAFgABAQEAAAAAAAAAAAAAAAAAAAcG/8QAFBAB"
    "AAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAAPwDSACXioCXioAD/2Q=="
)
IMAGES = [JPEG] * 10


def needs(key: str, name: str) -> pytest.MarkDecorator:
    return pytest.mark.skipif(
        SETTINGS.use_fakes or not key, reason=f"live: needs USE_FAKES=0 and {name}"
    )


gemini = needs(SETTINGS.gemini_api_key, "GEMINI_API_KEY")
claude = needs(SETTINGS.anthropic_api_key, "ANTHROPIC_API_KEY")
eleven = needs(SETTINGS.elevenlabs_api_key, "ELEVENLABS_API_KEY")
pytestmark = pytest.mark.live


@pytest.fixture
def pipe(tmp_path) -> Pipeline:
    return build_pipeline(replace(SETTINGS, data_dir=tmp_path))


def assert_real(client: object) -> None:
    assert not type(client).__name__.startswith("Fake"), "build_pipeline wired a fake"


def annotation() -> BatchAnnotation:
    return FakeAnnotator().annotate(IMAGES, TASK, 0.0)


def flagged() -> Assessment:
    return Assessment(suspicious=True, reason="The hands never touch the shirt.", confidence=0.7)


@gemini
def test_annotator(pipe):
    assert_real(pipe.annotator)
    a = pipe.annotator.annotate(IMAGES, TASK, 20.0)
    assert a.frames and a.summary
    assert all(f.timestamp_s >= 20.0 for f in a.frames)


@gemini
def test_comparer(pipe):
    assert_real(pipe.comparer)
    a = pipe.comparer.assess(pipe.start(TASK), annotation())
    assert a.reason and 0 <= a.confidence <= 1


@gemini
def test_judge(pipe):
    assert_real(pipe.judge)
    q = Question(text="Can you show the shirt to the camera?", batch_index=0)
    batch = Batch(
        index=0,
        started_at_s=0.0,
        image_paths=[],
        annotation=annotation(),
        assessment=flagged(),
        question=q,
    )
    session = Session(
        task=TASK,
        references=pipe.references.retrieve(TASK),
        batches=[batch],
        answers=[Answer(question_id=q.id, transcript="Sorry, I was holding my phone.")],
    )
    v = pipe.judge.verdict(session)
    assert v.decision in {"accept", "review", "reject"} and v.summary


@claude
def test_questioner(pipe):
    assert_real(pipe.questioner)
    text = pipe.questioner.ask(pipe.start(TASK), IMAGES, annotation(), flagged())
    assert text.strip()


@eleven
def test_speaker_into_transcriber(pipe):
    assert_real(pipe.speaker)
    assert_real(pipe.transcriber)
    audio = pipe.speaker.synthesize("I am folding the blue shirt on the kitchen table.")
    assert len(audio) > 1000
    transcript = pipe.transcriber.transcribe(audio, pipe.speaker.mime)
    assert "shirt" in transcript.lower()
