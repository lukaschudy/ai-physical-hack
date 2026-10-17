import { useState } from "react";
import { api } from "../api";
import type { Session } from "../types";

/** Contributor declares the intended task; creates the session. */
export default function TaskForm({ onStarted }: { onStarted: (s: Session) => void }) {
  const [task, setTask] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        api.createSession(task).then(onStarted);
      }}
    >
      <h1>What task are you recording?</h1>
      <input value={task} onChange={(e) => setTask(e.target.value)} placeholder="fold a t-shirt" />
      <button disabled={task.trim().length < 3}>Start</button>
    </form>
  );
}
