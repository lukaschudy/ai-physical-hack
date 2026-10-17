"""Astra: look at the original images + text + context and ask one targeted follow-up question."""

from typing import Protocol

from .models import Assessment, BatchAnnotation, Session


class Questioner(Protocol):
    def ask(
        self,
        session: Session,
        images: list[bytes],
        annotation: BatchAnnotation,
        assessment: Assessment,
    ) -> str: ...


class FakeQuestioner:
    def ask(self, session, images, annotation, assessment) -> str:
        return f"Can you show me your hands and describe what you are doing for: {session.task}?"


class ClaudeQuestioner:
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def ask(self, session, images, annotation, assessment) -> str:
        raise NotImplementedError
