export type SourceType = "pubmed" | "clinical_trials" | "fda_label" | "fda_adverse_event";

export type Workspace = {
  id: string;
  condition: string;
  intervention?: string | null;
  source_types: SourceType[];
  status: string;
  created_at: string;
};

export type EvidenceSource = {
  id: string;
  source_type: SourceType;
  external_id: string;
  title: string;
  abstract: string;
  url?: string | null;
  publication_date?: string | null;
  status?: string | null;
  phase?: string | null;
};

export type RetrievedChunk = {
  chunk_id: string;
  source_id: string;
  source_type: SourceType;
  citation: string;
  text: string;
  score: number;
  section: string;
  title: string;
  url?: string | null;
  external_id: string;
  publication_date?: string | null;
  status?: string | null;
  phase?: string | null;
  matched_terms: string[];
  relevance_note: string;
};

export type EvidenceExtraction = {
  id: string;
  workspace_id: string;
  source_id: string;
  source_type: SourceType;
  external_id: string;
  title: string;
  source_url?: string | null;
  publication_date?: string | null;
  authors: string[];
  citation: string;
  population_context: string;
  intervention: string;
  comparator: string;
  outcome_result: string;
  safety_note: string;
  supporting_quote: string;
  source_overview: string;
  methods_context: string;
  source_sections: string[];
  key_findings: string[];
  evidence_limitations: string[];
  source_understanding: string[];
  source_passages: string[];
  field_evidence: Record<string, string>;
  confidence: number;
  review_status: "unreviewed" | "reviewed" | "needs_review";
  has_quantitative_result: boolean;
  status?: string | null;
  phase?: string | null;
};

export type Answer = {
  id: string;
  question: string;
  previous_answer_id?: string | null;
  source_types?: SourceType[] | null;
  generation_mode?: "extractive" | "conversational";
  generation_note?: string;
  saved_to_brief?: boolean;
  short_answer: string;
  direct_answer: string;
  evidence_map: string[];
  reasoning_summary: string[];
  evidence_synthesis: string[];
  source_readouts: string[];
  evidence_quality: string[];
  facet_coverage: string[];
  answer_trace: { label: string; value: string; detail: string }[];
  evidence: string[];
  supporting_evidence: string[];
  safety_limitations: string[];
  uncertainty: string[];
  limitations: string[];
  citations: string[];
  retrieved_chunks: RetrievedChunk[];
};

export type Brief = {
  title: string;
  overview: string;
  source_summary: Record<string, number>;
  saved_answers: Answer[];
  review_summary: Record<string, number>;
  next_steps: string[];
  generated_at: string;
  key_claims: string[];
  evidence_gaps: string[];
  safety_note: string;
  citations: string[];
};

export type EvalReport = {
  generated_at: string;
  metrics: { name: string; score: number; description: string }[];
  scenarios: { name: string; question: string; expected: string; status: string }[];
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  (typeof window === "undefined" ? "http://127.0.0.1:8000" : `${window.location.protocol}//${window.location.hostname}:8000`);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export const api = {
  workspaces: () => request<Workspace[]>("/workspaces"),
  createWorkspace: (condition: string, intervention: string) =>
    request<Workspace>("/workspaces", {
      method: "POST",
      body: JSON.stringify({ condition, intervention: intervention || null }),
    }),
  ingest: (id: string) =>
    request<{ sources: number; chunks: number; extractions: number }>(`/workspaces/${id}/ingest`, { method: "POST" }),
  sources: (id: string) => request<EvidenceSource[]>(`/workspaces/${id}/sources`),
  extract: (id: string) =>
    request<{ extractions: number }>(`/workspaces/${id}/extract`, { method: "POST" }),
  extractions: (id: string) => request<EvidenceExtraction[]>(`/workspaces/${id}/extractions`),
  updateExtraction: (workspaceId: string, extractionId: string, reviewStatus: EvidenceExtraction["review_status"]) =>
    request<EvidenceExtraction>(`/workspaces/${workspaceId}/extractions/${extractionId}`, {
      method: "PATCH",
      body: JSON.stringify({ review_status: reviewStatus }),
    }),
  ask: (id: string, question: string, sourceTypes?: SourceType[] | null, mode: "workspace" | "document" = "workspace", sourceId?: string | null, previousAnswerId?: string | null) =>
    request<Answer>(`/workspaces/${id}/ask`, {
      method: "POST",
      body: JSON.stringify({ question, source_types: sourceTypes && sourceTypes.length > 0 ? sourceTypes : null, mode, source_id: sourceId ?? null, previous_answer_id: previousAnswerId ?? null }),
    }),
  answers: (id: string) => request<Answer[]>(`/workspaces/${id}/answers`),
  saveToBrief: (id: string, answerId: string, saved: boolean) => request<Answer>(`/workspaces/${id}/answers/${answerId}/brief?saved=${saved}`, { method: "PATCH" }),
  brief: (id: string) => request<Brief>(`/workspaces/${id}/brief`),
  evals: () => request<EvalReport>("/evals"),
};
