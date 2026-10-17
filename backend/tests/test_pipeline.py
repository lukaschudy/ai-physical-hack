"""Pipeline orchestration: failing external services and concurrent writes."""

import threading
from dataclasses import replace

import pytest

from app.annotate import FakeAnnotator
from app.astra import FakeQuestioner
from app.jev import FakeComparer
from app.models import Assessment
from app.pipeline import UNCHECKED, Conflict, Pipeline, Upstream
from app.references import JsonReferenceStore
from app.store import BlobStore, MemorySessionStore
from app.stt import FakeTranscriber
from app.tts import FakeSpeaker
from app.verdict import FakeJudge

IMAGES = [b"\xff\xd8fake"] * 10


class Boom:
    """Stands in for any external client: every call raises."""

    mime = "audio/wav"

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise RuntimeError(f"{name} is down")

        return fail


class AlwaysSuspicious:
    def assess(self, session, annotation) -> Assessment:
        return Assessment(suspicious=True, reason="Scene changed.", confidence=0.8)


@pytest.fixture
def pipe(tmp_path) -> Pipeline:
    return Pipeline(
        references=JsonReferenceStore(),
        annotator=FakeAnnotator(),
        comparer=AlwaysSuspicious(),
        questioner=FakeQuestioner(),
        speaker=FakeSpeaker(),
        transcriber=FakeTranscriber(),
        judge=FakeJudge(),
        sessions=MemorySessionStore(),
        blobs=BlobStore(tmp_path),
    )


def test_annotation_failure_stores_unchecked_batch(pipe, caplog):
    pipe = replace(pipe, annotator=Boom())
    s = pipe.start("fold a t-shirt")
    batch = pipe.process_batch(s.id, IMAGES)

    assert batch.annotation.frames == []
    assert not batch.assessment.suspicious and batch.question is None
    assert batch.assessment.reason.startswith(UNCHECKED)
    assert "annotation failed" in batch.assessment.reason
    assert len(batch.image_paths) == 10
    assert pipe.sessions.get(s.id).batches == [batch]
    assert "annotation failed" in caplog.text

    done = pipe.finish(s.id)
    assert done.verdict.decision == "review"  # FakeJudge would accept: nothing was flagged


def test_jev_failure_flags_for_review(pipe):
    pipe = replace(pipe, comparer=Boom())
    s = pipe.start("fold a t-shirt")
    batch = pipe.process_batch(s.id, IMAGES)

    assert batch.assessment.suspicious
    assert batch.assessment.reason.startswith(UNCHECKED)
    assert pipe.finish(s.id).verdict.decision == "review"


def test_unchecked_batches_do_not_soften_reject(pipe):
    pipe = replace(pipe, comparer=Boom())
    s = pipe.start("fold a t-shirt")
    for _ in range(4):
        pipe.process_batch(s.id, IMAGES)
    assert pipe.finish(s.id).verdict.decision == "reject"


@pytest.mark.parametrize("part", ["questioner", "speaker"])
def test_question_failure_keeps_batch_flagged(pipe, part, caplog):
    pipe = replace(pipe, **{part: Boom()})
    s = pipe.start("fold a t-shirt")
    batch = pipe.process_batch(s.id, IMAGES)

    assert batch.assessment.suspicious and batch.question is None
    assert pipe.sessions.get(s.id).batches == [batch]
    assert "follow-up question failed" in caplog.text


def test_transcription_failure_keeps_audio_and_allows_retry(pipe, tmp_path):
    broken = replace(pipe, transcriber=Boom())
    s = broken.start("fold a t-shirt")
    q = broken.process_batch(s.id, IMAGES).question

    with pytest.raises(Upstream):
        broken.answer(s.id, q.id, b"spoken", "audio/webm;codecs=opus")
    assert (tmp_path / f"sessions/{s.id}/answers/{q.id}.webm").read_bytes() == b"spoken"
    assert pipe.sessions.get(s.id).answers == []

    assert pipe.answer(s.id, q.id, b"spoken", "audio/webm").transcript


def test_judge_failure_keeps_session_active(pipe):
    s = pipe.start("fold a t-shirt")
    with pytest.raises(Upstream):
        replace(pipe, judge=Boom()).finish(s.id)
    assert pipe.sessions.get(s.id).status == "active"
    assert pipe.finish(s.id).status == "finished"


def test_answer_twice_conflicts(pipe):
    s = pipe.start("fold a t-shirt")
    q = pipe.process_batch(s.id, IMAGES).question
    pipe.answer(s.id, q.id, b"a", "audio/webm")
    with pytest.raises(Conflict, match="already answered"):
        pipe.answer(s.id, q.id, b"a", "audio/webm")


def test_captured_at_overrides_index_timestamp(pipe):
    s = pipe.start("fold a t-shirt")
    assert pipe.process_batch(s.id, IMAGES).started_at_s == 0
    batch = pipe.process_batch(s.id, IMAGES, captured_at_s=12.5)
    assert batch.started_at_s == 12.5
    assert batch.annotation.frames[0].timestamp_s == 12.5


class BlockingAnnotator(FakeAnnotator):
    def __init__(self):
        self.started, self.release = threading.Event(), threading.Event()

    def annotate(self, images, task, batch_start_s):
        self.started.set()
        assert self.release.wait(5)
        return super().annotate(images, task, batch_start_s)


def test_answer_during_slow_batch_keeps_both_writes(pipe):
    s = pipe.start("fold a t-shirt")
    q = pipe.process_batch(s.id, IMAGES).question
    slow = BlockingAnnotator()
    pipe.annotator = slow

    worker = threading.Thread(target=pipe.process_batch, args=(s.id, IMAGES))
    worker.start()
    assert slow.started.wait(5)
    pipe.answer(s.id, q.id, b"a", "audio/webm")  # must not wait for the batch
    slow.release.set()
    worker.join(5)

    session = pipe.sessions.get(s.id)
    assert [b.index for b in session.batches] == [0, 1]
    assert [a.question_id for a in session.answers] == [q.id]


def test_concurrent_batches_get_distinct_indexes(pipe):
    pipe = replace(pipe, comparer=FakeComparer())
    s = pipe.start("fold a t-shirt")
    workers = [threading.Thread(target=pipe.process_batch, args=(s.id, IMAGES)) for _ in range(6)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(5)
    assert [b.index for b in pipe.sessions.get(s.id).batches] == list(range(6))
