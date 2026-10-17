import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { formatTimer, MAX_ANSWER_S, pickMimeType } from "../lib/audio";
import type { Question } from "../types";

export interface QuestionPanelProps {
  sessionId: string;
  question: Question;
  audioUrl: string;
  onAnswered: () => void;
}

type Phase = "ready" | "recording" | "uploading" | "done";
type Failure = { kind: "mic" | "upload"; message: string };

/** How long the transcript stays visible before handing back to the recorder. */
const TRANSCRIPT_MS = 2500;

/** Plays Astra's question, records the spoken answer (tap to start/stop) and uploads it. */
export default function QuestionPanel({ sessionId, question, audioUrl, onAnswered }: QuestionPanelProps) {
  const [phase, setPhase] = useState<Phase>("ready");
  const [needsPlay, setNeedsPlay] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [failure, setFailure] = useState<Failure | null>(null);

  const audioEl = useRef<HTMLAudioElement>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const blob = useRef<Blob | null>(null);
  const timers = useRef<number[]>([]);
  const alive = useRef(true);
  const answered = useRef(onAnswered);
  answered.current = onAnswered;

  const clearTimers = () => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
  };
  const releaseMic = () => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  };

  // Autoplay the question; browsers without a prior user gesture reject play().
  useEffect(() => {
    const el = audioEl.current;
    if (!el) return;
    setNeedsPlay(false);
    el.play().catch(() => alive.current && setNeedsPlay(true));
  }, [audioUrl]);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      clearTimers();
      if (recorder.current?.state === "recording") recorder.current.stop();
      releaseMic();
    };
  }, []);

  const upload = async () => {
    if (!blob.current) return;
    setFailure(null);
    setPhase("uploading");
    try {
      const { answer } = await api.postAnswer(sessionId, question.id, blob.current);
      if (!alive.current) return;
      setTranscript(answer.transcript);
      setPhase("done");
      timers.current.push(window.setTimeout(() => answered.current(), TRANSCRIPT_MS));
    } catch (e) {
      if (!alive.current) return;
      setFailure({ kind: "upload", message: `Upload failed: ${e instanceof Error ? e.message : e}` });
      setPhase("ready");
    }
  };

  const start = async () => {
    setFailure(null);
    audioEl.current?.pause();
    let media: MediaStream;
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const denied = e instanceof DOMException && e.name === "NotAllowedError";
      setFailure({
        kind: "mic",
        message: denied ? "Microphone access was denied. Allow it in the browser and retry." : `Microphone unavailable: ${e}`,
      });
      return;
    }
    stream.current = media;
    if (!alive.current) return releaseMic();

    const mimeType = pickMimeType((m) => MediaRecorder.isTypeSupported(m));
    const rec = new MediaRecorder(media, mimeType ? { mimeType } : undefined);
    const chunks: Blob[] = [];
    rec.ondataavailable = (ev) => ev.data.size > 0 && chunks.push(ev.data);
    rec.onstop = () => {
      clearTimers();
      releaseMic();
      if (!alive.current) return;
      blob.current = new Blob(chunks, { type: rec.mimeType || mimeType || "audio/webm" });
      void upload();
    };
    recorder.current = rec;
    rec.start();

    const t0 = performance.now();
    setElapsed(0);
    setPhase("recording");
    timers.current.push(window.setInterval(() => setElapsed((performance.now() - t0) / 1000), 200));
    timers.current.push(window.setTimeout(() => rec.state === "recording" && rec.stop(), MAX_ANSWER_S * 1000));
  };

  const stop = () => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  };

  return (
    <section aria-live="polite">
      <p style={{ fontSize: "1.5rem", fontWeight: 600 }}>{question.text}</p>
      <audio ref={audioEl} src={audioUrl} preload="auto" onPlay={() => setNeedsPlay(false)} />
      {needsPlay && phase === "ready" && (
        <button onClick={() => audioEl.current?.play().catch(() => {})}>Play question</button>
      )}

      {phase === "ready" && !failure && <button onClick={start}>Answer by voice</button>}
      {phase === "recording" && (
        <>
          <button onClick={stop}>Stop</button>{" "}
          <span role="timer">
            Recording {formatTimer(elapsed)} / {formatTimer(MAX_ANSWER_S)}
          </span>
        </>
      )}
      {phase === "uploading" && <p>Transcribing…</p>}
      {phase === "done" && <p>You said: “{transcript}”</p>}

      {failure && (
        <div role="alert">
          <p>{failure.message}</p>
          <button onClick={failure.kind === "mic" ? start : upload}>Retry</button>
          {failure.kind === "upload" && <button onClick={start}>Record again</button>}
        </div>
      )}
    </section>
  );
}
