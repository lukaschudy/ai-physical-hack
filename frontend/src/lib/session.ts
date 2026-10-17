import type { Batch, Question, Session } from "../types";

/** Follow-up questions with no answer yet, oldest first. Derived from the session so they survive reloads. */
export function unansweredQuestions(session: Session): Question[] {
  const answered = new Set(session.answers.map((a) => a.question_id));
  return session.batches.flatMap((b) => (b.question && !answered.has(b.question.id) ? [b.question] : []));
}

export const questionAudioUrl = (sessionId: string, questionId: string) =>
  `/api/sessions/${sessionId}/questions/${questionId}/audio`;

/** Add a batch result unless a refetch already brought it in. */
export function withBatch(session: Session, batch: Batch): Session {
  if (session.batches.some((b) => b.id === batch.id)) return session;
  return { ...session, batches: [...session.batches, batch] };
}
