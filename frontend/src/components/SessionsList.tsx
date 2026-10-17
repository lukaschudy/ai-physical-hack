import { useEffect, useState } from "react";
import { api } from "../api";
import type { Session } from "../types";

/** TODO: reviewer table with decision/score badges. */
export default function SessionsList({ onOpen }: { onOpen: (id: string) => void }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  useEffect(() => {
    api.listSessions().then(setSessions);
  }, []);
  return (
    <ul>
      {sessions.map((s) => (
        <li key={s.id}>
          <button onClick={() => onOpen(s.id)}>{s.task}</button>
        </li>
      ))}
    </ul>
  );
}
