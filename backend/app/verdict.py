"""Jev's end-of-session verdict: fraud score, decision, evidence."""

from typing import Protocol

from .models import Evidence, Session, Verdict


class Judge(Protocol):
    def verdict(self, session: Session) -> Verdict: ...


def collect_evidence(session: Session) -> list[Evidence]:
    """Flagged batches with their reason and any follow-up Q&A."""
    answers = {a.question_id: a.transcript for a in session.answers}
    return [
        Evidence(
            batch_index=b.index,
            timestamp_s=b.started_at_s,
            reason=b.assessment.reason,
            question=b.question.text if b.question else None,
            answer=answers.get(b.question.id) if b.question else None,
        )
        for b in session.batches
        if b.assessment.suspicious
    ]


def decide(score: int) -> str:
    return "accept" if score < 30 else "review" if score < 70 else "reject"


class FakeJudge:
    def verdict(self, session: Session) -> Verdict:
        evidence = collect_evidence(session)
        score = min(100, 20 * len(evidence))
        return Verdict(
            fraud_score=score,
            decision=decide(score),
            summary=f"Fake: {len(evidence)} flagged batch(es) out of {len(session.batches)}.",
            evidence=evidence,
        )


class GeminiJudge:
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def verdict(self, session: Session) -> Verdict:
        raise NotImplementedError
