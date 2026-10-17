import { useState } from "react";
import { api } from "../api";
import type { Session } from "../types";

export const EXAMPLE_TASKS = ["fold a t-shirt", "wash dishes", "chop vegetables", "make a bed"];
export const MIN_TASK_LENGTH = 3; // backend CreateSessionRequest min_length

/** Turns an api.ts error ("<status> <body>") or a network failure into one readable line. */
export function errorText(e: unknown): string {
  if (e instanceof TypeError) return "Can't reach the server. Check your connection and try again.";
  const msg = e instanceof Error ? e.message : String(e);
  const m = msg.match(/^(\d{3}) ([\s\S]*)$/);
  if (!m) return msg;
  try {
    const detail: unknown = JSON.parse(m[2]).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg;
  } catch {
    // body was not JSON
  }
  return Number(m[1]) >= 500 ? "Server error. Try again in a moment." : m[2] || `Error ${m[1]}`;
}

/** Contributor declares the intended task; creates the session. */
export default function TaskForm({ onStarted }: { onStarted: (s: Session) => void }) {
  const [task, setTask] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = task.trim();

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        api.createSession(trimmed).then(onStarted, (err) => {
          setError(errorText(err));
          setLoading(false);
        });
      }}
    >
      <p className="eyebrow">New recording</p>
      <h1>What task are you about to record?</h1>
      <p className="muted">
        Describe it in a few words. Shift checks that the camera shows the task you name, and may
        ask you a quick spoken question while you work.
      </p>

      <div>
        <label htmlFor="task">Task</label>
        <input
          id="task"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="e.g. fold a t-shirt"
          autoComplete="off"
          enterKeyHint="go"
          disabled={loading}
        />
      </div>

      <div className="row" role="group" aria-label="Example tasks">
        {EXAMPLE_TASKS.map((t) => (
          <button
            key={t}
            type="button"
            className="chip"
            aria-pressed={trimmed === t}
            onClick={() => setTask(t)}
            disabled={loading}
          >
            {t}
          </button>
        ))}
      </div>

      {error && <p role="alert">{error}</p>}

      <button className="primary block" disabled={loading || trimmed.length < MIN_TASK_LENGTH}>
        {loading ? "Starting…" : "Start recording"}
      </button>
      <p className="muted small">Your browser will ask for camera and microphone access next.</p>
    </form>
  );
}
