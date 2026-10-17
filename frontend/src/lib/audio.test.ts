import { describe, expect, it } from "vitest";
import { extensionForMime, formatTimer, MIME_CANDIDATES, pickMimeType } from "./audio";

describe("pickMimeType", () => {
  it("prefers webm/opus", () => {
    expect(pickMimeType(() => true)).toBe("audio/webm;codecs=opus");
  });
  it("falls back to mp4 (Safari)", () => {
    expect(pickMimeType((m) => m === "audio/mp4")).toBe("audio/mp4");
  });
  it("returns undefined when nothing is supported", () => {
    expect(pickMimeType(() => false)).toBeUndefined();
  });
  it("checks candidates in order", () => {
    const seen: string[] = [];
    pickMimeType((m) => (seen.push(m), false));
    expect(seen).toEqual(MIME_CANDIDATES);
  });
});

describe("extensionForMime", () => {
  it.each([
    ["audio/webm;codecs=opus", "webm"],
    ["audio/webm", "webm"],
    ["audio/mp4", "m4a"],
    ["audio/mp4; codecs=mp4a.40.2", "m4a"],
    ["Audio/OGG;codecs=opus", "ogg"],
    ["audio/mpeg", "mp3"],
    ["", "webm"],
    ["application/octet-stream", "webm"],
  ])("%s -> %s", (mime, ext) => {
    expect(extensionForMime(mime)).toBe(ext);
  });
});

describe("formatTimer", () => {
  it.each([
    [0, "0:00"],
    [7.9, "0:07"],
    [30, "0:30"],
    [65, "1:05"],
    [-1, "0:00"],
  ])("%s -> %s", (s, out) => {
    expect(formatTimer(s)).toBe(out);
  });
});
