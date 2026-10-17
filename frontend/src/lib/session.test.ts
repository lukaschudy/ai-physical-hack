import { describe, expect, it } from "vitest";
import type { Batch, Session } from "../types";
import { questionAudioUrl, unansweredQuestions, withBatch } from "./session";

const batch = (index: number, questionId?: string): Batch => ({
  id: `b${index}`,
  index,
  started_at_s: index * 10,
  image_paths: [],
  annotation: { frames: [], summary: "" },
  assessment: { suspicious: !!questionId, reason: "", confidence: 0.5, checked: true },
  question: questionId ? { id: questionId, text: "?", batch_index: index, asked_at: "" } : null,
});

const session = (batches: Batch[], answered: string[] = []): Session => ({
  id: "s",
  task: "fold a t-shirt",
  created_at: "",
  status: "active",
  references: [],
  batches,
  answers: answered.map((question_id) => ({ question_id, transcript: "ok", answered_at: "" })),
  verdict: null,
});

describe("unansweredQuestions", () => {
  it("queues every unanswered question in batch order", () => {
    const s = session([batch(0, "q0"), batch(1), batch(2, "q2"), batch(3, "q3")], ["q2"]);
    expect(unansweredQuestions(s).map((q) => q.id)).toEqual(["q0", "q3"]);
  });
});

describe("withBatch", () => {
  it("appends new batches and ignores ones already present", () => {
    const s = session([batch(0)]);
    expect(withBatch(s, batch(1)).batches).toHaveLength(2);
    expect(withBatch(s, batch(0))).toBe(s);
  });
});

it("builds the question audio url", () => {
  expect(questionAudioUrl("s", "q")).toBe("/api/sessions/s/questions/q/audio");
});
