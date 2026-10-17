import { fileUrl } from "../api";
import {
  DECISION_HINT,
  DECISION_LABEL,
  REJECT_AT,
  REVIEW_AT,
  answerFor,
  clampScore,
  evidenceItems,
  formatPercent,
  formatTimestamp,
  plural,
  progressLine,
  scoreBand,
  sessionDuration,
} from "../lib/verdict";
import type { Batch, Decision, Session, Verdict } from "../types";
import css from "./verdict/verdict.module.css";

const ICON: Record<Decision, string> = { accept: "✓", review: "!", reject: "✕" };

/** Session verdict: decision, fraud score, evidence timeline and per-batch drill-down. */
export default function VerdictView({ session }: { session: Session }) {
  const v = session.verdict;
  return (
    <article className={css.root}>
      <header className={css.head}>
        <p className={css.eyebrow}>Session verdict</p>
        <h1 className={css.task}>{session.task}</h1>
        <p className={css.meta}>
          <span>#{session.id}</span>
          <span>{plural(session.batches.length, "batch", "batches")}</span>
          <span>{sessionDuration(session.batches)} recorded</span>
        </p>
      </header>

      {v ? <Outcome verdict={v} /> : <Pending session={session} />}
      {v && <Timeline session={session} />}
      <DrillDown session={session} />
    </article>
  );
}

function Outcome({ verdict }: { verdict: Verdict }) {
  const score = clampScore(verdict.fraud_score);
  const band = scoreBand(score);
  return (
    <section className={css.outcome} aria-label="Verdict">
      <div className={`${css.badge} ${css[verdict.decision]}`}>
        <span className={css.badgeIcon} aria-hidden>
          {ICON[verdict.decision]}
        </span>
        <span>
          <strong className={css.badgeLabel}>{DECISION_LABEL[verdict.decision]}</strong>
          <span className={css.badgeHint}>{DECISION_HINT[verdict.decision]}</span>
        </span>
      </div>

      <div className={css.score}>
        <p className={css.scoreValue}>
          {score}
          <span>/100 fraud score</span>
        </p>
        <div
          className={css.meter}
          role="meter"
          aria-label="Fraud score"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={score}
        >
          <div className={`${css.meterFill} ${css[band]}`} style={{ width: `${score}%` }} />
          <div className={css.tick} style={{ left: `${REVIEW_AT}%` }} />
          <div className={css.tick} style={{ left: `${REJECT_AT}%` }} />
        </div>
        <div className={css.scale} aria-hidden>
          <span style={{ left: 0 }}>0</span>
          <span style={{ left: `${REVIEW_AT}%` }}>{REVIEW_AT} review</span>
          <span style={{ left: `${REJECT_AT}%` }}>{REJECT_AT} reject</span>
          <span style={{ right: 0 }}>100</span>
        </div>
      </div>

      <p className={css.summary}>{verdict.summary}</p>
    </section>
  );
}

function Pending({ session }: { session: Session }) {
  const active = session.status === "active";
  return (
    <section className={css.pending} aria-label="Verdict">
      <span className={active ? css.pulse : css.dot} aria-hidden />
      <div>
        <strong>{active ? "Recording in progress" : "Verdict not available"}</strong>
        <p>
          {active
            ? "Jev issues the verdict when the contributor ends the task."
            : "This session finished without a verdict."}{" "}
          {progressLine(session)}.
        </p>
      </div>
    </section>
  );
}

function Timeline({ session }: { session: Session }) {
  const items = evidenceItems(session);
  return (
    <section className={css.section}>
      <h2 className={css.h2}>
        Evidence <span>{plural(items.length, "flagged batch", "flagged batches")}</span>
      </h2>
      {items.length === 0 ? (
        <p className={css.empty}>No batches were flagged.</p>
      ) : (
        <ol className={css.timeline}>
          {items.map(({ evidence: e, batch }) => (
            <li key={`${e.batch_index}-${e.timestamp_s}`} className={css.event}>
              <time className={css.stamp}>{formatTimestamp(e.timestamp_s)}</time>
              <div className={css.eventBody}>
                <p className={css.reason}>
                  <span className={css.batchTag}>Batch {e.batch_index + 1}</span>
                  {e.reason}
                </p>
                {batch && <Thumbs batch={batch} />}
                {e.question && (
                  <dl className={css.qa}>
                    <dt>Astra asked</dt>
                    <dd>{e.question}</dd>
                    <dt>Contributor said</dt>
                    <dd className={e.answer ? undefined : css.noAnswer}>
                      {e.answer ? `“${e.answer}”` : "No answer"}
                    </dd>
                  </dl>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Thumbs({ batch }: { batch: Batch }) {
  const frames = new Map(batch.annotation.frames.map((f) => [f.index, f]));
  return (
    <div className={css.thumbs}>
      {batch.image_paths.map((path, i) => {
        const frame = frames.get(i);
        const odd = (frame?.anomalies.length ?? 0) > 0;
        const at = formatTimestamp(frame?.timestamp_s ?? batch.started_at_s + i);
        return (
          <a
            key={path}
            href={fileUrl(path)}
            target="_blank"
            rel="noreferrer"
            className={odd ? `${css.thumb} ${css.thumbOdd}` : css.thumb}
            title={odd ? `${at} · ${frame!.anomalies.join(", ")}` : at}
          >
            <img src={fileUrl(path)} alt={`Frame ${i + 1} at ${at}`} loading="lazy" />
          </a>
        );
      })}
    </div>
  );
}

function DrillDown({ session }: { session: Session }) {
  if (session.batches.length === 0) return null;
  return (
    <section className={css.section}>
      <h2 className={css.h2}>
        Batches <span>Flash annotations</span>
      </h2>
      {session.batches.map((b) => (
        <BatchDetails key={b.id} session={session} batch={b} />
      ))}
    </section>
  );
}

function BatchDetails({ session, batch: b }: { session: Session; batch: Batch }) {
  const answer = answerFor(session, b);
  return (
    <details className={css.batch}>
      <summary className={css.batchSummary}>
        <time className={css.stamp}>{formatTimestamp(b.started_at_s)}</time>
        <span className={css.batchName}>Batch {b.index + 1}</span>
        <span className={b.assessment.suspicious || !b.assessment.checked ? css.flagged : css.clean}>
          {!b.assessment.checked
            ? "Not checked"
            : b.assessment.suspicious
              ? `Flagged · ${formatPercent(b.assessment.confidence)}`
              : "Clean"}
        </span>
        <span className={css.batchLine}>{b.annotation.summary}</span>
      </summary>

      <div className={css.batchBody}>
        <p>
          <b>Flash</b> {b.annotation.summary}
        </p>
        {b.assessment.reason && (
          <p>
            <b>Jev</b> {b.assessment.reason}
          </p>
        )}
        {b.question && (
          <p>
            <b>Astra</b> {b.question.text}{" "}
            <i className={answer ? undefined : css.noAnswer}>
              {answer ? `— “${answer}”` : "— no answer"}
            </i>
          </p>
        )}
        <Thumbs batch={b} />
        <div className={css.tableWrap}>
          <table className={css.frames}>
            <thead>
              <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Hands</th>
                <th>Objects</th>
                <th>Scene</th>
                <th>Anomalies</th>
              </tr>
            </thead>
            <tbody>
              {b.annotation.frames.map((f) => (
                <tr key={f.index} className={f.anomalies.length ? css.rowOdd : undefined}>
                  <td className={css.mono}>{formatTimestamp(f.timestamp_s)}</td>
                  <td>{f.action}</td>
                  <td>{f.hands || "—"}</td>
                  <td>{f.objects.join(", ") || "—"}</td>
                  <td>{f.scene || "—"}</td>
                  <td>{f.anomalies.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}
