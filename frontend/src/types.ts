// Mirrors backend/app/models.py. Change both together, additively.

export type Label = "legit" | "fraud";
export type Decision = "accept" | "review" | "reject";

export interface ReferenceAnnotation {
  id: string;
  task: string;
  label: Label;
  description: string;
  signals: string[];
}

export interface FrameAnnotation {
  index: number;
  timestamp_s: number;
  action: string;
  hands: string;
  objects: string[];
  scene: string;
  anomalies: string[];
}

export interface BatchAnnotation {
  frames: FrameAnnotation[];
  summary: string;
}

export interface Assessment {
  suspicious: boolean;
  reason: string;
  confidence: number;
}

export interface Question {
  id: string;
  text: string;
  batch_index: number;
  asked_at: string;
}

export interface Answer {
  question_id: string;
  transcript: string;
  answered_at: string;
}

export interface Batch {
  id: string;
  index: number;
  started_at_s: number;
  image_paths: string[];
  annotation: BatchAnnotation;
  assessment: Assessment;
  question: Question | null;
}

export interface Evidence {
  batch_index: number;
  timestamp_s: number;
  reason: string;
  question: string | null;
  answer: string | null;
}

export interface Verdict {
  fraud_score: number;
  decision: Decision;
  summary: string;
  evidence: Evidence[];
}

export interface Session {
  id: string;
  task: string;
  created_at: string;
  status: "active" | "finished";
  references: ReferenceAnnotation[];
  batches: Batch[];
  answers: Answer[];
  verdict: Verdict | null;
}

export interface BatchResult {
  batch: Batch;
  question_audio_url: string | null;
}

export interface AnswerResult {
  answer: Answer;
}
