import type { Session } from "../types";

/** TODO: score, decision, summary, evidence with batch images and Q&A. */
export default function VerdictView({ session }: { session: Session }) {
  const v = session.verdict;
  if (!v) return <p>No verdict yet.</p>;
  return (
    <section>
      <h1>
        {v.decision} — {v.fraud_score}/100
      </h1>
      <p>{v.summary}</p>
    </section>
  );
}
