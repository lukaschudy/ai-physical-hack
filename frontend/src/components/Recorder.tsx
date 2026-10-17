import type { BatchResult } from "../types";

export interface RecorderProps {
  sessionId: string;
  /** True while a follow-up question is pending: stop capturing. */
  paused: boolean;
  onBatch: (r: BatchResult) => void;
  onError: (msg: string) => void;
}

/** TODO: camera preview; capture 1 JPEG/s; every 10 frames call api.postBatch. */
export default function Recorder({ paused }: RecorderProps) {
  return <section>{paused ? "Paused for a question" : "Recorder not implemented"}</section>;
}
