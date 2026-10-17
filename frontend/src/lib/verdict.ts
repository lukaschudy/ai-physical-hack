// Pure formatting helpers for the session verdict view.

import type { Batch, Decision, Evidence, Session } from "../types";

/** Same thresholds as backend/app/verdict.py `decide`. */
export const REVIEW_AT = 30;
export const REJECT_AT = 70;

export const DECISION_LABEL: Record<Decision, string> = {
  accept: "Accept",
  review: "Review",
  reject: "Reject",
};

export const DECISION_HINT: Record<Decision, string> = {
  accept: "Recording is consistent with the declared task.",
  review: "Send to a human reviewer.",
  reject: "Recording looks fraudulent.",
};

/** Seconds since session start → "mm:ss" (minutes keep counting past 59). */
export function formatTimestamp(seconds: number): string {
  const s = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Integer in 0..100; non-numbers become 0. */
export function clampScore(score: number): number {
  return Number.isFinite(score) ? Math.min(100, Math.max(0, Math.round(score))) : 0;
}

/** Decision band a score falls into, for colouring the meter. */
export function scoreBand(score: number): Decision {
  const s = clampScore(score);
  return s < REVIEW_AT ? "accept" : s < REJECT_AT ? "review" : "reject";
}

/** 0..1 confidence → "82%". */
export function formatPercent(fraction: number): string {
  return `${Math.round(Math.min(1, Math.max(0, fraction || 0)) * 100)}%`;
}

/** Recording length covered by the batches, e.g. "00:40". */
export function sessionDuration(batches: Batch[]): string {
  const end = Math.max(0, ...batches.map((b) => b.started_at_s + 10));
  return formatTimestamp(end);
}

export interface EvidenceItem {
  evidence: Evidence;
  batch: Batch | undefined; // undefined if the batch is missing from the session
}

/** Verdict evidence joined with its batch (for thumbnails), in recording order. */
export function evidenceItems(session: Session): EvidenceItem[] {
  const byIndex = new Map(session.batches.map((b) => [b.index, b]));
  return [...(session.verdict?.evidence ?? [])]
    .sort((a, b) => a.timestamp_s - b.timestamp_s)
    .map((evidence) => ({ evidence, batch: byIndex.get(evidence.batch_index) }));
}

/** Transcribed answer to a batch's follow-up question, if any. */
export function answerFor(session: Session, batch: Batch): string | null {
  if (!batch.question) return null;
  const id = batch.question.id;
  return session.answers.find((a) => a.question_id === id)?.transcript ?? null;
}

/** "3 batches · 1 flagged · 1 question" style tally for sessions in progress. */
export function progressLine(session: Session): string {
  const n = session.batches.length;
  const flagged = session.batches.filter((b) => b.assessment.suspicious).length;
  const questions = session.batches.filter((b) => b.question).length;
  return [plural(n, "batch", "batches"), `${flagged} flagged`, plural(questions, "question")].join(
    " · ",
  );
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
