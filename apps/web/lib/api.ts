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
  source_type: SourceType;
  citation: string;
  text: string;
  score: number;
};

export type Answer = {
  id: string;
  question: string;
  short_answer: string;
  evidence: string[];
  limitations: string[];
  citations: string[];
  retrieved_chunks: RetrievedChunk[];
};

export type Brief = {
  title: string;
  overview: string;
  source_summary: Record<string, number>;
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
  createWorkspace: (condition: string, intervention: string) =>
    request<Workspace>("/workspaces", {
      method: "POST",
      body: JSON.stringify({ condition, intervention: intervention || null }),
    }),
  ingest: (id: string) => request<{ sources: number; chunks: number }>(`/workspaces/${id}/ingest`, { method: "POST" }),
  sources: (id: string) => request<EvidenceSource[]>(`/workspaces/${id}/sources`),
  ask: (id: string, question: string) =>
    request<Answer>(`/workspaces/${id}/ask`, { method: "POST", body: JSON.stringify({ question }) }),
  brief: (id: string) => request<Brief>(`/workspaces/${id}/brief`),
  evals: () => request<EvalReport>("/evals"),
};

