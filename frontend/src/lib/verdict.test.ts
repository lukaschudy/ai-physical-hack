import { describe, expect, it } from "vitest";
import { makeBatch, makeSession } from "../components/verdict/fixture";
import {
  answerFor,
  clampScore,
  evidenceItems,
  formatPercent,
  formatTimestamp,
  plural,
  progressLine,
  scoreBand,
  sessionDuration,
} from "./verdict";

describe("formatTimestamp", () => {
  it("pads minutes and seconds", () => {
    expect(formatTimestamp(0)).toBe("00:00");
    expect(formatTimestamp(9.9)).toBe("00:09");
    expect(formatTimestamp(70)).toBe("01:10");
  });
  it("keeps counting minutes past an hour", () => {
    expect(formatTimestamp(3725)).toBe("62:05");
  });
  it("treats negative and non-finite input as zero", () => {
    expect(formatTimestamp(-4)).toBe("00:00");
    expect(formatTimestamp(Number.NaN)).toBe("00:00");
  });
});

describe("clampScore / scoreBand", () => {
  it("clamps and rounds", () => {
    expect(clampScore(-5)).toBe(0);
    expect(clampScore(140)).toBe(100);
    expect(clampScore(44.6)).toBe(45);
    expect(clampScore(Number.NaN)).toBe(0);
  });
  it("matches backend thresholds", () => {
    expect(scoreBand(29)).toBe("accept");
    expect(scoreBand(30)).toBe("review");
    expect(scoreBand(69)).toBe("review");
    expect(scoreBand(70)).toBe("reject");
  });
});

describe("formatPercent", () => {
  it("rounds and clamps a fraction", () => {
    expect(formatPercent(0.824)).toBe("82%");
    expect(formatPercent(1.3)).toBe("100%");
    expect(formatPercent(-1)).toBe("0%");
  });
});

describe("sessionDuration", () => {
  it("ends 10 s after the last batch start", () => {
    expect(sessionDuration([makeBatch(0, false), makeBatch(3, false)])).toBe("00:40");
    expect(sessionDuration([])).toBe("00:00");
  });
});

describe("evidenceItems", () => {
  it("joins evidence with its batch in time order", () => {
    const s = makeSession();
    const ev = s.verdict!.evidence[0];
    s.verdict!.evidence = [
      { ...ev, batch_index: 1, timestamp_s: 10 },
      { ...ev, batch_index: 0, timestamp_s: 0 },
    ];
    const items = evidenceItems(s);
    expect(items.map((i) => i.batch?.id)).toEqual(["b0", "b1"]);
  });
  it("tolerates missing batches and missing verdicts", () => {
    const s = makeSession({ batches: [] });
    expect(evidenceItems(s)[0].batch).toBeUndefined();
    expect(evidenceItems(makeSession({ verdict: null }))).toEqual([]);
  });
});

describe("answerFor", () => {
  it("finds the transcript for the batch's question", () => {
    const s = makeSession();
    expect(answerFor(s, s.batches[1])).toBe("I moved to the other sink.");
    expect(answerFor(s, s.batches[0])).toBeNull();
    expect(answerFor({ ...s, answers: [] }, s.batches[1])).toBeNull();
  });
});

describe("progressLine / plural", () => {
  it("summarises an active session", () => {
    expect(progressLine(makeSession({ status: "active", verdict: null }))).toBe(
      "2 batches · 1 flagged · 1 question",
    );
    expect(progressLine(makeSession({ batches: [] }))).toBe("0 batches · 0 flagged · 0 questions");
  });
  it("pluralises", () => {
    expect(plural(1, "batch", "batches")).toBe("1 batch");
    expect(plural(2, "frame")).toBe("2 frames");
  });
});
