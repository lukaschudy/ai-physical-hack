import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import VerdictView from "../VerdictView";
import { makeSession } from "./fixture";

const render = (s = makeSession()) => renderToStaticMarkup(<VerdictView session={s} />);

describe("VerdictView", () => {
  it("shows decision, score, summary and evidence with thumbnails and Q&A", () => {
    const html = render();
    expect(html).toContain("Review");
    expect(html).toContain('aria-valuenow="45"');
    expect(html).toContain("One flagged batch, answer plausible.");
    expect(html).toContain("00:10");
    expect(html).toContain("Scene changed mid-task");
    expect(html).toContain("/api/files/s1/1/9.jpg");
    expect(html).toContain("Why did the room change?");
    expect(html).toContain("I moved to the other sink.");
  });

  it("says no answer when the question went unanswered", () => {
    const s = makeSession({ answers: [] });
    s.verdict!.evidence[0].answer = null;
    expect(render(s)).toContain("No answer");
  });

  it("handles an active session without a verdict", () => {
    const html = render(makeSession({ status: "active", verdict: null }));
    expect(html).toContain("Recording in progress");
    expect(html).toContain("2 batches · 1 flagged · 1 question");
    expect(html).not.toContain('role="meter"');
    expect(html).toContain("Batch 1 summary"); // drill-down still available
  });

  it("handles an empty session", () => {
    const html = render(makeSession({ status: "active", verdict: null, batches: [] }));
    expect(html).toContain("0 batches");
  });
});
