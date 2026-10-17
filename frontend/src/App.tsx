import { useEffect, useState } from "react";
import QuestionPanel from "./components/QuestionPanel";
import Recorder from "./components/Recorder";
import SessionsList from "./components/SessionsList";
import TaskForm from "./components/TaskForm";
import VerdictView from "./components/VerdictView";
import { api } from "./api";
import { questionAudioUrl, unansweredQuestions, withBatch } from "./lib/session";
import type { BatchResult, Session } from "./types";

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

const ACTIVE_KEY = "shift.activeSession";

/** The active session id lives in sessionStorage so switching to Review and back resumes it. */
function ContributorFlow() {
  const [session, setSession] = useState<Session | null>(null);
  const [restoring, setRestoring] = useState(() => sessionStorage.getItem(ACTIVE_KEY) !== null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = sessionStorage.getItem(ACTIVE_KEY);
    if (!id) return;
    api
      .getSession(id)
      .then(setSession, () => sessionStorage.removeItem(ACTIVE_KEY))
      .finally(() => setRestoring(false));
  }, []);

  const start = (s: Session) => {
    sessionStorage.setItem(ACTIVE_KEY, s.id);
    setSession(s);
  };
  const reset = () => {
    sessionStorage.removeItem(ACTIVE_KEY);
    setSession(null);
    setError(null);
  };

  if (restoring) return <p className="muted">Loading…</p>;
  if (!session) return <TaskForm onStarted={start} />;
  if (session.status === "finished")
    return (
      <div className="stack">
        <VerdictView session={session} />
        <button className="block" onClick={reset}>
          Record another task
        </button>
      </div>
    );

  // Questions queue up if several batches get flagged; ask them one at a time.
  const question = unansweredQuestions(session)[0];
  const onBatch = (r: BatchResult) => setSession((s) => (s ? withBatch(s, r.batch) : s));
  const onAnswered = () => api.getSession(session.id).then(setSession, (e) => setError(String(e)));
  const finish = () => api.finish(session.id).then(setSession, (e) => setError(String(e)));

  return (
    <div className="stack">
      <div>
        <p className="eyebrow">Recording</p>
        <h1>{session.task}</h1>
      </div>
      <Recorder sessionId={session.id} paused={!!question} onBatch={onBatch} onError={setError} />
      {question && (
        <QuestionPanel
          key={question.id}
          sessionId={session.id}
          question={question}
          audioUrl={questionAudioUrl(session.id, question.id)}
          onAnswered={onAnswered}
        />
      )}
      {error && <p role="alert">{error}</p>}
      <button className="block" onClick={finish} disabled={!!question}>
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
