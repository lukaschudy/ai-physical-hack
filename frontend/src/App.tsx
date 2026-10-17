import { useEffect, useState } from "react";
import QuestionPanel from "./components/QuestionPanel";
import Recorder from "./components/Recorder";
import SessionsList from "./components/SessionsList";
import TaskForm from "./components/TaskForm";
import VerdictView from "./components/VerdictView";
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
  const reviewing = hash.startsWith("#/sessions");
  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/">
          <span className="brand-mark" aria-hidden="true" />
          Shift
        </a>
        <nav className="tabs" aria-label="Main">
          <a href="#/" aria-current={reviewing ? undefined : "page"}>
            Record
          </a>
          <a href="#/sessions" aria-current={reviewing ? "page" : undefined}>
            Review
          </a>
        </nav>
      </header>
      <main className={reviewing ? "wide" : undefined}>
        {reviewId ? (
          <ReviewSession id={reviewId} />
        ) : reviewing ? (
          <SessionsList onOpen={(id) => (location.hash = `#/sessions/${id}`)} />
        ) : (
          <ContributorFlow />
        )}
      </main>
    </>
  );
}

function ContributorFlow() {
  const [session, setSession] = useState<Session | null>(null);
  const [pending, setPending] = useState<{ question: Question; audioUrl: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!session) return <TaskForm onStarted={setSession} />;
  if (session.status === "finished") return <VerdictView session={session} />;

  const onBatch = (r: BatchResult) => {
    setSession((s) => (s ? { ...s, batches: [...s.batches, r.batch] } : s));
    if (r.batch.question && r.question_audio_url)
      setPending({ question: r.batch.question, audioUrl: r.question_audio_url });
  };

  const finish = () => api.finish(session.id).then(setSession, (e) => setError(String(e)));

  return (
    <div className="stack">
      <div>
        <p className="eyebrow">Recording</p>
        <h1>{session.task}</h1>
      </div>
      <Recorder sessionId={session.id} paused={pending !== null} onBatch={onBatch} onError={setError} />
      {pending && (
        <QuestionPanel
          sessionId={session.id}
          question={pending.question}
          audioUrl={pending.audioUrl}
          onAnswered={() => setPending(null)}
        />
      )}
      {error && <p role="alert">{error}</p>}
      <button className="block" onClick={finish} disabled={pending !== null}>
        Finish task
      </button>
    </div>
  );
}

function ReviewSession({ id }: { id: string }) {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    api.getSession(id).then(setSession);
  }, [id]);
  return (
    <div className="stack">
      <a href="#/sessions">← All sessions</a>
      {session ? <VerdictView session={session} /> : <p className="muted">Loading…</p>}
    </div>
  );
}
