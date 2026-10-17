// Pure helpers for the Shift recorder: batching, sizing, retries, status text.
import type { Batch } from "../types";

export const BATCH_SIZE = 10; // must match backend main.BATCH_SIZE
export const FRAME_INTERVAL_MS = 1000;
export const FRAME_WIDTH = 640;
export const JPEG_QUALITY = 0.7;

/** Rear camera first (phones), then any camera. */
export const CAMERA_CONSTRAINTS: MediaStreamConstraints[] = [
  { video: { facingMode: { ideal: "environment" } }, audio: false },
  { video: true, audio: false },
];

/** Append a frame; when the buffer reaches `size`, return it as a full batch and start over. */
export function addFrame<T>(buffer: T[], frame: T, size = BATCH_SIZE): { buffer: T[]; batch: T[] | null } {
  const next = [...buffer, frame];
  return next.length >= size ? { buffer: [], batch: next } : { buffer: next, batch: null };
}

/** Scale to at most `maxWidth` wide, keeping aspect ratio. */
export function frameSize(videoWidth: number, videoHeight: number, maxWidth = FRAME_WIDTH) {
  const scale = Math.min(1, maxWidth / videoWidth);
  return { width: Math.round(videoWidth * scale), height: Math.round(videoHeight * scale) };
}

/** Run `fn`, retrying up to `retries` more times on failure. */
export async function withRetry<T>(fn: () => Promise<T>, retries = 1): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (attempt >= retries) throw e;
    }
  }
}

/** Try each constraint set in order; throw the last error if none works. */
export async function openCamera(
  getUserMedia: (c: MediaStreamConstraints) => Promise<MediaStream>,
  constraints = CAMERA_CONSTRAINTS,
): Promise<MediaStream> {
  let last: unknown;
  for (const c of constraints) {
    try {
      return await getUserMedia(c);
    } catch (e) {
      last = e;
      // Permission denial won't change with other constraints.
      if (errorName(e) === "NotAllowedError") break;
    }
  }
  throw last;
}

export function cameraErrorMessage(e: unknown): string {
  switch (errorName(e)) {
    case "NotAllowedError":
      return "Camera access denied. Allow camera permission and reload.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No camera found.";
    case "NotReadableError":
      return "Camera is in use by another app.";
    default:
      return `Camera error: ${e instanceof Error ? e.message : String(e)}`;
  }
}

/** Jev's take on a batch: "ok" or "flagged: <reason>". */
export function jevResultText(batch: Batch): string {
  const a = batch.assessment;
  return a.suspicious ? `flagged: ${a.reason || "no reason given"}` : "ok";
}

export function formatClock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function errorName(e: unknown): string | undefined {
  return typeof e === "object" && e !== null && "name" in e ? String(e.name) : undefined;
}
