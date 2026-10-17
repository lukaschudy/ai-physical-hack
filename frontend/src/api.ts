import { extensionForMime } from "./lib/audio";
import type { AnswerResult, BatchResult, Session } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const fileUrl = (rel: string) => `/api/files/${rel}`;

export const api = {
  createSession: (task: string) =>
    request<Session>("/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task }),
    }),

  listSessions: () => request<Session[]>("/sessions"),

  getSession: (id: string) => request<Session>(`/sessions/${id}`),

  /** Exactly 10 JPEG frames. */
  postBatch: (id: string, frames: Blob[]) => {
    const body = new FormData();
    frames.forEach((f, i) => body.append("images", f, `${i}.jpg`));
    return request<BatchResult>(`/sessions/${id}/batches`, { method: "POST", body });
  },

  /** Recorded answer; filename extension follows the blob's mime (webm or m4a). */
  postAnswer: (id: string, questionId: string, audio: Blob) => {
    const body = new FormData();
    body.append("question_id", questionId);
    body.append("audio", audio, `answer.${extensionForMime(audio.type)}`);
    return request<AnswerResult>(`/sessions/${id}/answers`, { method: "POST", body });
  },

  finish: (id: string) => request<Session>(`/sessions/${id}/finish`, { method: "POST" }),
};
