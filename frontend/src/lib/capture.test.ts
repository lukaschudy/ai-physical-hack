import { describe, expect, it, vi } from "vitest";
import type { Batch } from "../types";
import {
  BATCH_SIZE,
  CAMERA_CONSTRAINTS,
  addFrame,
  cameraErrorMessage,
  formatClock,
  frameSize,
  jevResultText,
  openCamera,
  withRetry,
} from "./capture";

const domError = (name: string) => Object.assign(new Error(name), { name });

describe("addFrame", () => {
  it("emits a batch every BATCH_SIZE frames and resets", () => {
    let buffer: number[] = [];
    const batches: number[][] = [];
    for (let i = 0; i < 25; i++) {
      const r = addFrame(buffer, i);
      buffer = r.buffer;
      if (r.batch) batches.push(r.batch);
    }
    expect(batches).toEqual([
      [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
      [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
    ]);
    expect(buffer).toEqual([20, 21, 22, 23, 24]);
    expect(BATCH_SIZE).toBe(10);
  });

  it("does not mutate the input buffer", () => {
    const buffer = [1, 2];
    addFrame(buffer, 3);
    expect(buffer).toEqual([1, 2]);
  });
});

describe("frameSize", () => {
  it("scales down to 640 wide keeping aspect", () => {
    expect(frameSize(1920, 1080)).toEqual({ width: 640, height: 360 });
    expect(frameSize(1080, 1920)).toEqual({ width: 640, height: 1138 });
  });
  it("never upscales", () => {
    expect(frameSize(320, 240)).toEqual({ width: 320, height: 240 });
  });
});

describe("withRetry", () => {
  it("retries once then succeeds", async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce("ok");
    await expect(withRetry(fn)).resolves.toBe("ok");
    expect(fn).toHaveBeenCalledTimes(2);
  });
  it("throws the last error after one retry", async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error("a")).mockRejectedValueOnce(new Error("b"));
    await expect(withRetry(fn)).rejects.toThrow("b");
    expect(fn).toHaveBeenCalledTimes(2);
  });
});

describe("openCamera", () => {
  const stream = {} as MediaStream;

  it("prefers the environment camera", async () => {
    const gum = vi.fn().mockResolvedValue(stream);
    await expect(openCamera(gum)).resolves.toBe(stream);
    expect(gum).toHaveBeenCalledWith(CAMERA_CONSTRAINTS[0]);
    expect(gum).toHaveBeenCalledTimes(1);
  });
  it("falls back to any camera", async () => {
    const gum = vi.fn().mockRejectedValueOnce(domError("OverconstrainedError")).mockResolvedValueOnce(stream);
    await expect(openCamera(gum)).resolves.toBe(stream);
    expect(gum).toHaveBeenLastCalledWith({ video: true, audio: false });
  });
  it("stops trying after permission denial", async () => {
    const gum = vi.fn().mockRejectedValue(domError("NotAllowedError"));
    await expect(openCamera(gum)).rejects.toMatchObject({ name: "NotAllowedError" });
    expect(gum).toHaveBeenCalledTimes(1);
  });
});

describe("cameraErrorMessage", () => {
  it("maps DOM error names", () => {
    expect(cameraErrorMessage(domError("NotAllowedError"))).toMatch(/denied/);
    expect(cameraErrorMessage(domError("NotFoundError"))).toMatch(/No camera/);
    expect(cameraErrorMessage(new Error("weird"))).toBe("Camera error: weird");
  });
});

describe("jevResultText", () => {
  const batch = (suspicious: boolean, reason: string) =>
    ({ assessment: { suspicious, reason, confidence: 0.9 } }) as Batch;
  it("shows ok or the flag reason", () => {
    expect(jevResultText(batch(false, "fine"))).toBe("ok");
    expect(jevResultText(batch(true, "hands not visible"))).toBe("flagged: hands not visible");
  });
});

describe("formatClock", () => {
  it("formats mm:ss", () => {
    expect(formatClock(0)).toBe("00:00");
    expect(formatClock(75)).toBe("01:15");
  });
});
