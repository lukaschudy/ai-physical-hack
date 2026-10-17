import { useEffect, useState } from "react";
import { api } from "../api";
import type { Decision, Session } from "../types";
import { errorText } from "./TaskForm";

export const REFRESH_MS = 5000;

export interface SessionRow {
  id: string;
  task: string;
  createdAt: string;
  live: boolean;
  decision: Decision | null;
  score: number | null;
  batches: number;
  flags: number;
}

/** Newest first; does not mutate the input. */
export function sortNewestFirst(sessions: Session[]): Session[] {
  return [...sessions].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

export function toRow(s: Session): SessionRow {
  return {
    id: s.id,
    task: s.task,
    createdAt: s.created_at,
    live: s.status === "active",
    decision: s.verdict?.decision ?? null,
    score: s.verdict?.fraud_score ?? null,
    batches: s.batches.length,
    flags: s.batches.filter((b) => b.assessment.suspicious).length,
  };
}

const dateFmt = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** Reviewer table of all sessions, polled every REFRESH_MS. */
export default function SessionsList({ onOpen }: { onOpen: (id: string) => void }) {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.listSessions().then(
        (s) => {
          if (!alive) return;
          setSessions(sortNewestFirst(s));
          setError(null);
        },
        (e) => alive && setError(errorText(e)),
      );
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const rows = sessions?.map(toRow) ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Review</p>
          <h1>Sessions</h1>
        </div>
        <p className="muted small mono">
          {sessions ? `${rows.length} total · ` : ""}refreshes every {REFRESH_MS / 1000} s
        </p>
      </div>

      {error && (
        <p role="alert">
          {sessions ? "Couldn't refresh; showing the last loaded list." : "Couldn't load sessions."}{" "}
          <span className="mono small">{error}</span>
        </p>
      )}

      {sessions === null ? (
        !error && <p className="muted">Loading sessions…</p>
      ) : rows.length === 0 ? (
        <div className="empty stack">
          <h2>No sessions yet</h2>
          <p className="muted">
            Recordings appear here as soon as a contributor starts one.{" "}
            <a href="#/">Start a recording</a>
          </p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="cards">
            <thead>
              <tr>
                <th>Task</th>
                <th>Started</th>
                <th>Status</th>
                <th>Decision</th>
                <th className="num">Score</th>
                <th className="num">Batches</th>
                <th className="num">Flags</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="clickable" onClick={() => onOpen(r.id)}>
                  <td>
                    {/* No handler: the click bubbles to the row; the button gives keyboard access. */}
                    <button className="link">{r.task}</button>
                  </td>
                  <td data-label="Started" className="mono small">
                    {dateFmt.format(new Date(r.createdAt))}
                  </td>
                  <td data-label="Status">
                    <span className={r.live ? "badge live" : "badge"}>
                      {r.live ? "Live" : "Finished"}
                    </span>
                  </td>
                  <td data-label="Decision">
                    {r.decision ? (
                      <span className={`badge ${r.decision}`}>{r.decision}</span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td data-label="Score" className="num">
                    {r.score ?? <span className="muted">—</span>}
                  </td>
                  <td data-label="Batches" className="num">
                    {r.batches}
                  </td>
                  <td data-label="Flags" className={r.flags > 0 ? "num flagged" : "num"}>
                    {r.flags}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
