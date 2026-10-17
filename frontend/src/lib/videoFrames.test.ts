import { describe, expect, it } from "vitest";
import { createBatcher, fitSize, sampleStep } from "./videoFrames";

/** Feed a sequence of video times through sampleStep; return the times that were sampled. */
function sampled(times: number[]): number[] {
  let next = 0;
  const out: number[] = [];
  for (const t of times) {
    const n = sampleStep(next, t);
    if (n === null) continue;
    out.push(t);
    next = n;
  }
  return out;
}

describe("sampleStep", () => {
  it("samples once per second of video time", () => {
    const ticks = Array.from({ length: 200 }, (_, i) => i / 60); // 60 fps, 3.3 s
    expect(sampled(ticks).map(Math.floor)).toEqual([0, 1, 2, 3]);
  });

  it("is not due before the next second", () => {
    expect(sampleStep(3, 2.99)).toBeNull();
    expect(sampleStep(3, 3)).toBe(4);
  });

  it("skips missed seconds instead of bursting", () => {
    expect(sampled([0, 0.5, 4.2, 4.3, 5.01])).toEqual([0, 4.2, 5.01]);
  });

  it("supports other intervals", () => {
    expect(sampleStep(1, 0.4, 0.5)).toBeNull();
    expect(sampleStep(1, 0.5, 0.5)).toBe(2);
  });
});

describe("createBatcher", () => {
  it("emits full batches and drops the remainder", () => {
    const b = createBatcher<number>(10);
    const batches = Array.from({ length: 25 }, (_, i) => b.push(i)).filter((x) => x !== null);
    expect(batches).toEqual([
      [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
      [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
    ]);
    expect(b.drop()).toBe(5);
    expect(b.drop()).toBe(0);
  });
});

describe("fitSize", () => {
  it("keeps small frames and scales large ones", () => {
    expect(fitSize(320, 240)).toEqual([320, 240]);
    expect(fitSize(1920, 1080)).toEqual([640, 360]);
    expect(fitSize(1080, 1920, 540)).toEqual([540, 960]);
  });
});
