"""Orchestrates one contributor session: declare -> batches -> follow-ups -> verdict.

External calls (Flash, Jev, Astra, TTS, STT, verdict) may fail. A failed check never drops a batch:
it is stored and marked "Not checked", and such sessions are never auto-accepted.
"""

import logging
import threading
from dataclasses import dataclass, field

from .annotate import Annotator
from .astra import Questioner
from .jev import Comparer
from .models import Answer, Assessment, Batch, BatchAnnotation, Question, Session, Verdict
from .references import ReferenceStore
from .store import BlobStore, SessionStore
from .stt import Transcriber
from .tts import Speaker
from .verdict import Judge

log = logging.getLogger(__name__)

BATCH_SECONDS = 10.0
AUDIO_EXT = {"audio/mpeg": "mp3", "audio/wav": "wav"}
ANSWER_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", **AUDIO_EXT}
UNCHECKED = "Not checked:"  # assessment reason prefix when Flash or Jev failed


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class Upstream(Exception):
    """An external service failed and nothing sensible could be stored; the client may retry."""


@dataclass
class _SessionLocks:
    batch: threading.Lock = field(default_factory=threading.Lock)  # one batch at a time, in order
    state: threading.Lock = field(default_factory=threading.Lock)  # short read-modify-write


def failed_annotation(error: Exception) -> tuple[BatchAnnotation, Assessment]:
    return BatchAnnotation(frames=[], summary="Annotation unavailable."), Assessment(
        suspicious=False,
        reason=f"{UNCHECKED} annotation failed ({type(error).__name__}).",
        confidence=0,
    )


def failed_assessment(error: Exception) -> Assessment:
    return Assessment(
        suspicious=True,
        reason=f"{UNCHECKED} Jev comparison failed ({type(error).__name__}); needs human review.",
        confidence=0.5,
    )


def require_review(session: Session, verdict: Verdict) -> Verdict:
    """Batches that could not be checked must not pass silently: never auto-accept them."""
    unchecked = [b for b in session.batches if b.assessment.reason.startswith(UNCHECKED)]
    if not unchecked or verdict.decision != "accept":
        return verdict
    note = f"{len(unchecked)} batch(es) could not be checked automatically."
    return verdict.model_copy(update={"decision": "review", "summary": f"{verdict.summary} {note}"})


def answered(session: Session, question_id: str) -> bool:
    return any(a.question_id == question_id for a in session.answers)


@dataclass
class Pipeline:
    references: ReferenceStore
    annotator: Annotator
    comparer: Comparer
    questioner: Questioner
    speaker: Speaker
    transcriber: Transcriber
    judge: Judge
    sessions: SessionStore
    blobs: BlobStore
    _locks: dict[str, _SessionLocks] = field(default_factory=dict, init=False, repr=False)
    _guard: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _lock(self, session_id: str) -> _SessionLocks:
        with self._guard:
            return self._locks.setdefault(session_id, _SessionLocks())

    def _active(self, session_id: str) -> Session:
        session = self.sessions.get(session_id)
        if session is None:
            raise NotFound(session_id)
        if session.status != "active":
            raise Conflict("session already finished")
        return session

    def start(self, task: str) -> Session:
        session = Session(task=task, references=self.references.retrieve(task))
        self.sessions.save(session)
        return session

    def process_batch(
        self, session_id: str, images: list[bytes], captured_at_s: float | None = None
    ) -> Batch:
        locks = self._lock(session_id)
        # Batches are serialized so each sees the previous one in its context. The state lock is
        # only held to commit, so answers are not blocked by slow external calls.
        with locks.batch:
            session = self._active(session_id)
            index = len(session.batches)
            start_s = index * BATCH_SECONDS if captured_at_s is None else captured_at_s
            paths = [
                self.blobs.put(f"sessions/{session.id}/batch_{index:03d}/{i:02d}.jpg", img)
                for i, img in enumerate(images)
            ]
            annotation, assessment = self._check(session, images, start_s, index)
            question = None
            if assessment.suspicious:
                question = self._ask(session, images, annotation, assessment, index)
            batch = Batch(
                index=index,
                started_at_s=start_s,
                image_paths=paths,
                annotation=annotation,
                assessment=assessment,
                question=question,
            )
            with locks.state:
                session = self._active(session_id)
                session.batches.append(batch)
                self.sessions.save(session)
            return batch

    def _check(
        self, session: Session, images: list[bytes], start_s: float, index: int
    ) -> tuple[BatchAnnotation, Assessment]:
        try:
            annotation = self.annotator.annotate(images, session.task, start_s)
        except Exception as e:
            log.exception("annotation failed: session %s batch %d", session.id, index)
            return failed_annotation(e)
        try:
            return annotation, self.comparer.assess(session, annotation)
        except Exception as e:
            log.exception("Jev comparison failed: session %s batch %d", session.id, index)
            return annotation, failed_assessment(e)

    def _ask(
        self,
        session: Session,
        images: list[bytes],
        annotation: BatchAnnotation,
        assessment: Assessment,
        index: int,
    ) -> Question | None:
        """Astra's voiced follow-up, or None if Astra or TTS fail (the batch stays flagged)."""
        try:
            text = self.questioner.ask(session, images, annotation, assessment)
            audio = self.speaker.synthesize(text)
        except Exception:
            log.exception("follow-up question failed: session %s batch %d", session.id, index)
            return None
        question = Question(text=text, batch_index=index)
        ext = AUDIO_EXT.get(self.speaker.mime, "bin")
        self.blobs.put(f"sessions/{session.id}/questions/{question.id}.{ext}", audio)
        return question

    def question_audio(self, session_id: str, question_id: str) -> tuple[bytes, str]:
        session = self.sessions.get(session_id)
        if session is None or session.question(question_id) is None:
            raise NotFound(question_id)
        for mime, ext in AUDIO_EXT.items():
            path = self.blobs.path(f"sessions/{session_id}/questions/{question_id}.{ext}")
            if path.exists():
                return path.read_bytes(), mime
        raise NotFound(question_id)

    def _unanswered(self, session_id: str, question_id: str) -> Session:
        session = self._active(session_id)
        if session.question(question_id) is None:
            raise NotFound(question_id)
        if answered(session, question_id):
            raise Conflict("question already answered")
        return session

    def answer(self, session_id: str, question_id: str, audio: bytes, mime: str) -> Answer:
        session = self._unanswered(session_id, question_id)
        # Keep the spoken answer even if transcription fails.
        ext = ANSWER_EXT.get(mime.split(";")[0].strip(), "bin")
        self.blobs.put(f"sessions/{session.id}/answers/{question_id}.{ext}", audio)
        try:
            transcript = self.transcriber.transcribe(audio, mime)
        except Exception as e:
            log.exception("transcription failed: session %s question %s", session_id, question_id)
            raise Upstream("transcription failed, please retry") from e
        answer = Answer(question_id=question_id, transcript=transcript)
        with self._lock(session_id).state:
            session = self._unanswered(session_id, question_id)
            session.answers.append(answer)
            self.sessions.save(session)
        return answer

    def finish(self, session_id: str) -> Session:
        locks = self._lock(session_id)
        with locks.batch, locks.state:  # waits for an in-flight batch so the verdict includes it
            session = self._active(session_id)
            try:
                verdict = self.judge.verdict(session)
            except Exception as e:
                log.exception("verdict failed: session %s", session_id)
                raise Upstream("verdict failed, please retry") from e
            session.verdict = require_review(session, verdict)
            session.status = "finished"
            self.sessions.save(session)
            return session
