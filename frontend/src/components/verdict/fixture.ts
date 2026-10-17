// Test fixture: a finished session with one clean and one flagged, answered batch.

import type { Batch, Session } from "../../types";

export function makeBatch(index: number, suspicious: boolean, questionId?: string): Batch {
  const start = index * 10;
  return {
    id: `b${index}`,
    index,
    started_at_s: start,
    image_paths: Array.from({ length: 10 }, (_, i) => `s1/${index}/${i}.jpg`),
    annotation: {
      summary: `Batch ${index} summary`,
      frames: Array.from({ length: 10 }, (_, i) => ({
        index: i,
        timestamp_s: start + i,
        action: `action ${i}`,
        hands: "both hands on mug",
        objects: ["mug", "sponge"],
        scene: "kitchen sink",
        anomalies: suspicious && i === 3 ? ["scene change"] : [],
      })),
    },
    assessment: { suspicious, reason: suspicious ? "Scene changed mid-task" : "", confidence: 0.82, checked: true },
    question: questionId
      ? { id: questionId, text: "Why did the room change?", batch_index: index, asked_at: "" }
      : null,
  };
}

export function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    id: "s1",
    task: "Wash a mug",
    created_at: "2026-10-17T12:00:00Z",
    status: "finished",
    references: [],
    batches: [makeBatch(0, false), makeBatch(1, true, "q1")],
    answers: [{ question_id: "q1", transcript: "I moved to the other sink.", answered_at: "" }],
    verdict: {
      fraud_score: 45,
      decision: "review",
      summary: "One flagged batch, answer plausible.",
      evidence: [
        {
          batch_index: 1,
          timestamp_s: 10,
          reason: "Scene changed mid-task",
          question: "Why did the room change?",
          answer: "I moved to the other sink.",
        },
      ],
    },
    ...overrides,
  };
}
