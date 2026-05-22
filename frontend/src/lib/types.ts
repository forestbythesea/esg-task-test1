export type Confidence = "high" | "medium" | "low";

export type Source = {
  document_name: string;
  page: number;
  quote: string;
};

export type QuestionAnswer = {
  question: string;
  status: "answered" | "not_found";
  answer: string | null;
  confidence: Confidence;
  sources: Source[];
  missing_information?: string | null;
};

export type RiskScore = {
  dimension: string;
  score: number;
  confidence: Confidence;
  rationale: string;
  sources: Source[];
};

export type Company = {
  id: string;
  name: string;
  report_year: string;
  file_name: string;
  source_url: string;
  source_type: "baseline" | "upload";
  document_label?: string | null;
  status: string;
  generation_mode?: string | null;
  summary: { answer: string; sources: Source[] } | null;
  questions: QuestionAnswer[];
  risk_scores: RiskScore[];
  updated_at: string | null;
};

export type Run = {
  id: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  output_path?: string | null;
  error?: string | null;
};

export type Trace = {
  id: string;
  step: string;
  model: string;
  reasoning_effort: string;
  total_tokens: number;
  estimated_cost_usd: number;
  latency_ms: number;
  status: string;
};

export type ConfigStatus = {
  openai_configured: boolean;
  model: string;
  model_validated: boolean;
  generation_mode: string;
  error?: string | null;
};
