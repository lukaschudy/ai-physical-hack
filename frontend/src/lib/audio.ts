/** Longest spoken answer we record before auto-stopping. */
export const MAX_ANSWER_S = 30;

/** Preferred MediaRecorder formats, best first (Chrome/Firefox: webm/opus, Safari: mp4). */
export const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/mp4"];

/** First supported candidate, or undefined to let the browser pick its default. */
export function pickMimeType(
  isSupported: (mime: string) => boolean,
  candidates: string[] = MIME_CANDIDATES,
): string | undefined {
  return candidates.find((m) => isSupported(m));
}

const EXTENSIONS: Record<string, string> = {
  "audio/webm": "webm",
  "audio/mp4": "m4a",
  "audio/ogg": "ogg",
  "audio/mpeg": "mp3",
  "audio/wav": "wav",
};

/** File extension for a (possibly parameterized) mime, e.g. "audio/webm;codecs=opus" -> "webm". */
export function extensionForMime(mime: string): string {
  const base = mime.split(";")[0].trim().toLowerCase();
  return EXTENSIONS[base] ?? "webm";
}

/** Seconds as m:ss, e.g. 7.9 -> "0:07". */
export function formatTimer(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
