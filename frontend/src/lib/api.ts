import type { Company, ConfigStatus, Run, Trace } from "./types";

const API_BASE = "";

export function getToken() {
  return localStorage.getItem("esg_token");
}

export function setToken(token: string) {
  localStorage.setItem("esg_token", token);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("esg_token");
      throw new Error("Session expired. Refresh and sign in again.");
    }
    throw new Error((await response.json().catch(() => ({}))).detail ?? response.statusText);
  }
  return response.json();
}

export async function login(username: string) {
  const result = await request<{ token: string; user: { display_name: string; role: string } }>(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ username }) }
  );
  setToken(result.token);
  return result.user;
}

export const fetchCompanies = () => request<Company[]>("/api/companies");
export const fetchConfigStatus = () => request<ConfigStatus>("/api/config/status");
export const runIngestion = () => request<{ run_id: string; status: string }>("/api/ingest/run", { method: "POST" });
export const processReport = (reportId: string) =>
  request<{ run_id: string; status: string }>(`/api/reports/${reportId}/process`, { method: "POST" });
export const uploadReport = (formData: FormData) =>
  request<Company>("/api/reports/upload", { method: "POST", body: formData });
export const fetchRuns = () => request<Run[]>("/api/runs");
export const fetchObservability = (runId: string) =>
  request<{ run: Run; totals: Record<string, number>; traces: Trace[] }>(`/api/observability/runs/${runId}`);
export const sendChat = (companyId: string, message: string) =>
  request<{
    answer: string;
    confidence: string;
    citations: { document_name: string; page: number; quote: string }[];
    trace_id: string;
    token_usage: Record<string, number>;
    latency_ms: number;
    reasoning_effort: string;
  }>("/api/chat", { method: "POST", body: JSON.stringify({ company_id: companyId, message }) });
