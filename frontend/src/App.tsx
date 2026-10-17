import { useEffect, useState } from "react";
import QuestionPanel from "./components/QuestionPanel";
import Recorder from "./components/Recorder";
import SessionsList from "./components/SessionsList";
import TaskForm from "./components/TaskForm";
import VerdictView from "./components/VerdictView";
import VideoReplay from "./components/VideoReplay";
import { api } from "./api";
import type { BatchResult, Question, Session } from "./types";

/** Hash routes: "" = contributor flow, "#/sessions" = review list, "#/sessions/<id>" = one session. */
function useHash() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const on = () => setHash(location.hash);
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHash();
  const reviewId = hash.match(/^#\/sessions\/(\w+)/)?.[1];
  if (reviewId) return <ReviewSession id={reviewId} />;
  if (hash.startsWith("#/sessions"))
    return (
      <main>
        <SessionsList onOpen={(id) => (location.hash = `#/sessions/${id}`)} />
      </main>
    );
  return <ContributorFlow />;
}

function ContributorFlow() {
  const [session, setSession] = useState<Session | null>(null);
  const [pending, setPending] = useState<{ question: Question; audioUrl: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"camera" | "video">("camera");

  if (!session) return <main><TaskForm onStarted={setSession} /></main>;
  if (session.status === "finished") return <main><VerdictView session={session} /></main>;

  const onBatch = (r: BatchResult) => {
    setSession((s) => (s ? { ...s, batches: [...s.batches, r.batch] } : s));
    if (r.batch.question && r.question_audio_url)
      setPending({ question: r.batch.question, audioUrl: r.question_audio_url });
  };

  const finish = () => api.finish(session.id).then(setSession, (e) => setError(String(e)));

  return (
    <main>
      <h1>{session.task}</h1>
      <fieldset>
        <legend>Source</legend>
        {(["camera", "video"] as const).map((s) => (
          <label key={s}>
            <input type="radio" checked={source === s} onChange={() => setSource(s)} />
            {s === "camera" ? "Camera" : "Video file"}
          </label>
        ))}
      </fieldset>
      {source === "camera" ? (
        <Recorder sessionId={session.id} paused={pending !== null} onBatch={onBatch} onError={setError} />
      ) : (
        <VideoReplay sessionId={session.id} paused={pending !== null} onBatch={onBatch} onError={setError} />
      )}
      {pending && (
        <QuestionPanel
          sessionId={session.id}
          question={pending.question}
          audioUrl={pending.audioUrl}
          onAnswered={() => setPending(null)}
        />
      )}
      <button onClick={finish} disabled={pending !== null}>
        Finish task
      </button>
      {error && <p role="alert">{error}</p>}
    </main>
  );
}

function ReviewSession({ id }: { id: string }) {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    api.getSession(id).then(setSession);
  }, [id]);
  return <main>{session ? <VerdictView session={session} /> : <p>Loading…</p>}</main>;
}
