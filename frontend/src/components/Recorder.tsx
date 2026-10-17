import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import {
  FRAME_INTERVAL_MS,
  JPEG_QUALITY,
  addFrame,
  cameraErrorMessage,
  formatClock,
  frameSize,
  jevResultText,
  openCamera,
  withRetry,
} from "../lib/capture";
import type { Batch, BatchResult } from "../types";

export interface RecorderProps {
  sessionId: string;
  /** True while a follow-up question is pending: stop capturing. */
  paused: boolean;
  onBatch: (r: BatchResult) => void;
  onError: (msg: string) => void;
}

/** Camera preview; capture 1 JPEG/s; every 10 frames call api.postBatch without blocking capture. */
export default function Recorder({ sessionId, paused, onBatch, onError }: RecorderProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [sent, setSent] = useState(0);
  const [pending, setPending] = useState(0);
  const [failed, setFailed] = useState(0);
  const [last, setLast] = useState<Batch | null>(null);

  // Parent passes fresh callbacks each render; keep them out of effect deps.
  const onBatchRef = useRef(onBatch);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onBatchRef.current = onBatch;
    onErrorRef.current = onError;
  });

  // Open the camera once; stop its tracks on unmount.
  useEffect(() => {
    let cancelled = false;
    let stream: MediaStream | null = null;
    const gum = (c: MediaStreamConstraints) =>
      navigator.mediaDevices
        ? navigator.mediaDevices.getUserMedia(c)
        : Promise.reject(new Error("camera API unavailable (needs HTTPS or localhost)"));
    openCamera(gum).then(
      (s) => {
        if (cancelled) return s.getTracks().forEach((t) => t.stop());
        stream = s;
        const video = videoRef.current;
        if (video) {
          video.srcObject = s;
          video.play().catch(() => {}); // autoplay+muted normally covers this
        }
        setReady(true);
      },
      (e) => {
        if (cancelled) return;
        const msg = cameraErrorMessage(e);
        setCameraError(msg);
        onErrorRef.current(msg);
      },
    );
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
      setReady(false);
    };
  }, []);

  // Capture loop. Runs only while not paused; the partial batch lives in this closure,
  // so pausing (effect cleanup) discards it and resuming starts a fresh batch.
  useEffect(() => {
    if (!ready || paused) return;
    let active = true;
    let buffer: Blob[] = [];
    const canvas = document.createElement("canvas");

    const send = (frames: Blob[]) => {
      setPending((n) => n + 1);
      withRetry(() => api.postBatch(sessionId, frames))
        .then(
          (r) => {
            setSent((n) => n + 1);
            setLast(r.batch);
            onBatchRef.current(r);
          },
          (e) => {
            setFailed((n) => n + 1);
            onErrorRef.current(`Batch upload failed: ${e instanceof Error ? e.message : String(e)}`);
          },
        )
        .finally(() => setPending((n) => n - 1));
    };

    const id = setInterval(() => {
      const video = videoRef.current;
      if (!video || video.videoWidth === 0) return; // no frame yet
      const { width, height } = frameSize(video.videoWidth, video.videoHeight);
      canvas.width = width;
      canvas.height = height;
      canvas.getContext("2d")?.drawImage(video, 0, 0, width, height);
      setSeconds((s) => s + 1);
      canvas.toBlob(
        (blob) => {
          if (!active || !blob) return; // paused/unmounted while encoding
          const r = addFrame(buffer, blob);
          buffer = r.buffer;
          if (r.batch) send(r.batch);
        },
        "image/jpeg",
        JPEG_QUALITY,
      );
    }, FRAME_INTERVAL_MS);

    return () => {
      active = false;
      clearInterval(id);
    };
  }, [ready, paused, sessionId]);

  const recording = ready && !paused;
  return (
    <section>
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        style={{ width: "100%", maxHeight: "60vh", background: "#000", borderRadius: 8 }}
      />
      <p aria-live="polite">
        <span
          style={{
            display: "inline-block",
            width: 10,
            height: 10,
            borderRadius: "50%",
            marginRight: 6,
            background: recording ? "#dc2626" : "#9ca3af",
          }}
        />
        {cameraError ? cameraError : !ready ? "Starting camera…" : paused ? "Paused for a question" : "Recording"}
        {" · "}
        {formatClock(seconds)} · {sent} sent · {pending} pending
        {failed > 0 && ` · ${failed} failed`}
      </p>
      {last && (
        <p style={{ color: last.assessment.suspicious ? "#b91c1c" : "#15803d" }}>
          Jev (batch {last.index + 1}): {jevResultText(last)}
        </p>
      )}
    </section>
  );
}
