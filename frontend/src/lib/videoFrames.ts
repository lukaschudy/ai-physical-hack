// Helpers for sampling a played video file into JPEG batches (used by VideoReplay).

export const FRAME_INTERVAL_S = 1;
export const BATCH_SIZE = 10;
export const MAX_FRAME_WIDTH = 640;

/**
 * Sample `next` is due once the video time reaches next * interval.
 * Returns the index of the following sample if one is due now, else null.
 * Skips past any samples missed while the page wasn't rendering.
 */
export function sampleStep(next: number, timeS: number, interval = FRAME_INTERVAL_S): number | null {
  if (timeS < next * interval) return null;
  return Math.floor(timeS / interval) + 1;
}

/** Collects frames; push returns a full batch every `size` frames. */
export function createBatcher<T>(size = BATCH_SIZE) {
  let buf: T[] = [];
  return {
    push(item: T): T[] | null {
      buf.push(item);
      if (buf.length < size) return null;
      const batch = buf;
      buf = [];
      return batch;
    },
    /** Discard the incomplete last batch; returns how many frames were dropped. */
    drop(): number {
      const n = buf.length;
      buf = [];
      return n;
    },
  };
}

/** Scale (w, h) down to at most maxWidth wide, keeping the aspect ratio. */
export function fitSize(w: number, h: number, maxWidth = MAX_FRAME_WIDTH): [number, number] {
  if (w <= maxWidth) return [w, h];
  return [maxWidth, Math.round((h * maxWidth) / w)];
}

/** Snapshot the current video frame as a JPEG. The canvas bitmap is copied synchronously. */
export function captureFrame(video: HTMLVideoElement, canvas: HTMLCanvasElement): Promise<Blob> {
  [canvas.width, canvas.height] = fitSize(video.videoWidth, video.videoHeight);
  canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("frame capture failed"))), "image/jpeg", 0.85),
  );
}
