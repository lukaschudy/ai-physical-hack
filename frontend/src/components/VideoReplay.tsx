import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { BATCH_SIZE, captureFrame, createBatcher, sampleStep } from "../lib/videoFrames";
import type { RecorderProps } from "./Recorder";

/** Recorder stand-in for demos: plays a local video file and sends 1 frame per video second. */
export default function VideoReplay({ sessionId, paused, onBatch, onError }: RecorderProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [sent, setSent] = useState(0);
  const [uploading, setUploading] = useState(0);
  const [dropped, setDropped] = useState<number | null>(null); // set when the video ends
  const latest = useRef({ sessionId, onBatch, onError });
  latest.current = { sessionId, onBatch, onError };

  useEffect(() => () => void (url && URL.revokeObjectURL(url)), [url]);

  // Sample while the video plays; batches go out in capture order.
  useEffect(() => {
    const video = videoRef.current;
    if (!url || !video) return;
    const canvas = document.createElement("canvas");
    const batcher = createBatcher<Promise<Blob>>();
    let next = 0;
    let raf = 0;

    const send = (frames: Promise<Blob>[]) => {
      setUploading((n) => n + 1);
      Promise.all(frames)
        .then((blobs) => api.postBatch(latest.current.sessionId, blobs))
        .then(
          (r) => {
            setSent((n) => n + 1);
            latest.current.onBatch(r);
          },
          (e) => latest.current.onError(String(e)),
        )
        .finally(() => setUploading((n) => n - 1));
    };

    const tick = () => {
      raf = requestAnimationFrame(tick);
      if (video.paused || video.ended || video.readyState < video.HAVE_CURRENT_DATA) return;
      const n = sampleStep(next, video.currentTime);
      if (n === null) return;
      next = n;
      const batch = batcher.push(captureFrame(video, canvas));
      if (batch) send(batch);
    };
    const onEnded = () => setDropped(batcher.drop());

    raf = requestAnimationFrame(tick);
    video.addEventListener("ended", onEnded);
    return () => {
      cancelAnimationFrame(raf);
      video.removeEventListener("ended", onEnded);
    };
  }, [url]);

  useEffect(() => {
    const video = videoRef.current;
    if (!url || !video || video.ended) return;
    if (paused) video.pause();
    else
      video.play().catch((e: unknown) => {
        // pause() interrupting a pending play() is expected
        if (!(e instanceof DOMException && e.name === "AbortError")) latest.current.onError(String(e));
      });
  }, [paused, url]);

  const pick = (file: File | undefined) => {
    if (!file) return;
    setUrl(URL.createObjectURL(file));
    setSent(0);
    setDropped(null);
  };

  const playing = url !== null && dropped === null;
  let status = "Choose a video file to replay";
  if (dropped !== null)
    status =
      `Video finished: ${sent} batch${sent === 1 ? "" : "es"} sent` +
      (dropped ? `, last ${dropped} frame${dropped === 1 ? "" : "s"} dropped (incomplete batch)` : "") +
      (uploading ? `, ${uploading} uploading…` : "");
  else if (paused && url) status = "Paused for a question";
  else if (url) status = `Replaying: ${sent} batch${sent === 1 ? "" : "es"} sent, 1 frame/s, ${BATCH_SIZE} per batch`;

  return (
    <section>
      <input
        type="file"
        accept="video/*"
        aria-label="Video file"
        disabled={playing}
        onChange={(e) => pick(e.target.files?.[0])}
      />
      {url && (
        <div>
          <video ref={videoRef} src={url} muted playsInline width={480} />
        </div>
      )}
      <p>{status}</p>
    </section>
  );
}
