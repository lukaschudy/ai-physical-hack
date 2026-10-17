"""Jev: compare a batch's live annotations with the task references and session context."""

from typing import Protocol

from .models import Assessment, BatchAnnotation, Session


class Comparer(Protocol):
    def assess(self, session: Session, annotation: BatchAnnotation) -> Assessment: ...


class FakeComparer:
    """Deterministic: flags every third batch so the demo exercises the question flow."""

    def assess(self, session: Session, annotation: BatchAnnotation) -> Assessment:
        if len(session.batches) % 3 == 2:
            return Assessment(suspicious=True, reason="Fake: periodic check-in.", confidence=0.6)
        return Assessment(suspicious=False, reason="Consistent with the task.", confidence=0.1)


class GeminiComparer:
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def assess(self, session: Session, annotation: BatchAnnotation) -> Assessment:
        raise NotImplementedError
