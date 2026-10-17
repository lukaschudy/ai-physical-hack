"""Shared domain types. The API contract with the frontend (mirrored in frontend/src/types.ts).

Change additively only: new fields need defaults so other modules keep working.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid4().hex[:12]


def now() -> datetime:
    return datetime.now(UTC)


Label = Literal["legit", "fraud"]
Decision = Literal["accept", "review", "reject"]


class ReferenceAnnotation(BaseModel):
    """A labelled example from MicroAGI's reference database."""

    id: str
    task: str
    label: Label
    description: str  # what happens in the recording, in Flash-annotation style
    signals: list[str] = []  # cues that make it legit / fraudulent


class FrameAnnotation(BaseModel):
    index: int  # 0..9 within the batch
    timestamp_s: float  # seconds since session start
    action: str  # what the contributor is doing
    hands: str = ""  # hand position / what they hold
    objects: list[str] = []
    scene: str = ""  # location / scene; scene changes are a fraud signal
    anomalies: list[str] = []  # anything odd: screen replay, static frame, cut, other person


class BatchAnnotation(BaseModel):
    """Gemini Flash's structured text for one 10-image batch."""

    frames: list[FrameAnnotation]
    summary: str


class Assessment(BaseModel):
    """Jev's per-batch judgement."""

    suspicious: bool
    reason: str
    confidence: float = Field(ge=0, le=1)  # confidence that something is wrong


class Question(BaseModel):
    id: str = Field(default_factory=new_id)
    text: str
    batch_index: int
    asked_at: datetime = Field(default_factory=now)


class Answer(BaseModel):
    question_id: str
    transcript: str
    answered_at: datetime = Field(default_factory=now)


class Batch(BaseModel):
    id: str = Field(default_factory=new_id)
    index: int
    started_at_s: float  # seconds since session start
    image_paths: list[str]  # stored originals, relative to DATA_DIR
    annotation: BatchAnnotation
    assessment: Assessment
    question: Question | None = None


class Evidence(BaseModel):
    batch_index: int
    timestamp_s: float
    reason: str
    question: str | None = None
    answer: str | None = None


class Verdict(BaseModel):
    fraud_score: int = Field(ge=0, le=100)
    decision: Decision
    summary: str
    evidence: list[Evidence] = []


class Session(BaseModel):
    id: str = Field(default_factory=new_id)
    task: str
    created_at: datetime = Field(default_factory=now)
    status: Literal["active", "finished"] = "active"
    references: list[ReferenceAnnotation] = []
    batches: list[Batch] = []
    answers: list[Answer] = []
    verdict: Verdict | None = None

    def question(self, question_id: str) -> Question | None:
        return next(
            (b.question for b in self.batches if b.question and b.question.id == question_id), None
        )


# --- API payloads ---


class CreateSessionRequest(BaseModel):
    task: str = Field(min_length=3)


class BatchResult(BaseModel):
    batch: Batch
    question_audio_url: str | None = None  # set when Astra asked a question


class AnswerResult(BaseModel):
    answer: Answer
