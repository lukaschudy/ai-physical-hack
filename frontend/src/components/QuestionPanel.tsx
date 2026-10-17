import type { Question } from "../types";

export interface QuestionPanelProps {
  sessionId: string;
  question: Question;
  audioUrl: string;
  onAnswered: () => void;
}

/** TODO: autoplay the question audio, record the spoken answer, api.postAnswer. */
export default function QuestionPanel({ question }: QuestionPanelProps) {
  return <section>{question.text}</section>;
}
