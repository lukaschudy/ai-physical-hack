"""Orchestrates one contributor session: declare -> batches -> follow-ups -> verdict."""

from dataclasses import dataclass

from .annotate import Annotator
from .astra import Questioner
from .jev import Comparer
from .models import Answer, Batch, Question, Session
from .references import ReferenceStore
from .store import BlobStore, SessionStore
from .stt import Transcriber
from .tts import Speaker
from .verdict import Judge

BATCH_SECONDS = 10.0
AUDIO_EXT = {"audio/mpeg": "mp3", "audio/wav": "wav"}


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


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

    def process_batch(self, session_id: str, images: list[bytes]) -> Batch:
        session = self._active(session_id)
        index = len(session.batches)
        start_s = index * BATCH_SECONDS
        paths = [
            self.blobs.put(f"sessions/{session.id}/batch_{index:03d}/{i:02d}.jpg", img)
            for i, img in enumerate(images)
        ]
        annotation = self.annotator.annotate(images, session.task, start_s)
        assessment = self.comparer.assess(session, annotation)
        question = None
        if assessment.suspicious:
            text = self.questioner.ask(session, images, annotation, assessment)
            question = Question(text=text, batch_index=index)
            audio = self.speaker.synthesize(text)
            ext = AUDIO_EXT.get(self.speaker.mime, "bin")
            self.blobs.put(f"sessions/{session.id}/questions/{question.id}.{ext}", audio)
        batch = Batch(
            index=index,
            started_at_s=start_s,
            image_paths=paths,
            annotation=annotation,
            assessment=assessment,
            question=question,
        )
        session.batches.append(batch)
        self.sessions.save(session)
        return batch

    def question_audio(self, session_id: str, question_id: str) -> tuple[bytes, str]:
        session = self.sessions.get(session_id)
        if session is None or session.question(question_id) is None:
            raise NotFound(question_id)
        for mime, ext in AUDIO_EXT.items():
            path = self.blobs.path(f"sessions/{session_id}/questions/{question_id}.{ext}")
            if path.exists():
                return path.read_bytes(), mime
        raise NotFound(question_id)

    def answer(self, session_id: str, question_id: str, audio: bytes, mime: str) -> Answer:
        session = self._active(session_id)
        if session.question(question_id) is None:
            raise NotFound(question_id)
        answer = Answer(
            question_id=question_id, transcript=self.transcriber.transcribe(audio, mime)
        )
        session.answers.append(answer)
        self.sessions.save(session)
        return answer

    def finish(self, session_id: str) -> Session:
        session = self._active(session_id)
        session.verdict = self.judge.verdict(session)
        session.status = "finished"
        self.sessions.save(session)
        return session
