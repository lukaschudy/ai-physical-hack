import { describe, expect, it } from "vitest";
import type { Batch, Session } from "../types";
import { sortNewestFirst, toRow } from "./SessionsList";

const batch = (suspicious: boolean): Batch => ({
  id: "b",
  index: 0,
  started_at_s: 0,
  image_paths: [],
  annotation: { frames: [], summary: "" },
  assessment: { suspicious, reason: "", confidence: 0.5 },
  question: null,
});

const session = (id: string, created_at: string, extra: Partial<Session> = {}): Session => ({
  id,
  task: "fold a t-shirt",
  created_at,
  status: "active",
  references: [],
  batches: [],
  answers: [],
  verdict: null,
  ...extra,
});

describe("sortNewestFirst", () => {
  it("orders by created_at descending without mutating input", () => {
    const input = [
      session("a", "2026-10-17T10:00:00Z"),
      session("c", "2026-10-17T12:00:00.5+00:00"),
      session("b", "2026-10-17T11:00:00Z"),
    ];
    expect(sortNewestFirst(input).map((s) => s.id)).toEqual(["c", "b", "a"]);
    expect(input.map((s) => s.id)).toEqual(["a", "c", "b"]);
  });
});

describe("toRow", () => {
  it("counts batches and flagged batches", () => {
    const row = toRow(
      session("a", "2026-10-17T10:00:00Z", { batches: [batch(false), batch(true), batch(true)] }),
    );
    expect(row).toMatchObject({ live: true, batches: 3, flags: 2, decision: null, score: null });
  });

  it("reads decision and score from the verdict", () => {
    const row = toRow(
      session("a", "2026-10-17T10:00:00Z", {
        status: "finished",
        verdict: { fraud_score: 0, decision: "accept", summary: "", evidence: [] },
      }),
    );
    expect(row).toMatchObject({ live: false, decision: "accept", score: 0 });
  });
});
