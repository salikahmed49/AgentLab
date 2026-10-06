import type { ResearchResult, Stage, UploadedDocument } from "./types";

const API_URL_CANDIDATES = [
  process.env.NEXT_PUBLIC_API_URL,
  "http://localhost:8001",
  "http://localhost:8000",
].filter((value): value is string => Boolean(value));

async function resolveApiBaseUrl(): Promise<string> {
  const uniqueCandidates = [...new Set(API_URL_CANDIDATES)];

  for (const candidate of uniqueCandidates) {
    try {
      const res = await fetch(`${candidate}/health`, { cache: "no-store" });
      if (res.ok) {
        return candidate;
      }
    } catch {
      // This port is not usable; try the next candidate.
    }
  }

  return uniqueCandidates[0] ?? "http://localhost:8000";
}

type ResearchJobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  current_step: Stage | null;
  completed_steps: Stage[];
  partial_result?: ResearchResult;
  result?: ResearchResult;
  error?: string;
};

export type HealthStatus = {
  status: "healthy" | "degraded";
  checks: {
    groq: boolean;
    gemini: boolean;
    ollama: boolean;
    tavily: boolean;
    llm: boolean;
    provider: string;
  };
  message: string;
};

export class ApiError extends Error {
  step?: Stage;
  constructor(message: string, step?: Stage) {
    super(message);
    this.step = step;
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const baseUrl = await resolveApiBaseUrl();
    const res = await fetch(`${baseUrl}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function getHealthStatus(): Promise<HealthStatus> {
  const baseUrl = await resolveApiBaseUrl();
  const res = await fetch(`${baseUrl}/health`, { cache: "no-store" });

  if (!res.ok) {
    throw new ApiError("The backend health check failed.");
  }

  return (await res.json()) as HealthStatus;
}

export async function uploadDocuments(files: File[]): Promise<UploadedDocument[]> {
  if (files.length === 0) return [];

  const baseUrl = await resolveApiBaseUrl();
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const res = await fetch(`${baseUrl}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail ?? "The uploaded document could not be processed.");
  }

  const body = (await res.json()) as { documents: UploadedDocument[] };
  return body.documents ?? [];
}

export async function startResearchJob(topic: string, documents: UploadedDocument[] = []): Promise<{ job_id: string; status: string }> {
  const baseUrl = await resolveApiBaseUrl();
  const res = await fetch(`${baseUrl}/research/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, documents }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail ?? "The research job could not be started.");
  }

  return (await res.json()) as { job_id: string; status: string };
}

export async function getResearchJobStatus(jobId: string): Promise<ResearchJobStatus> {
  const baseUrl = await resolveApiBaseUrl();
  const res = await fetch(`${baseUrl}/research/jobs/${jobId}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail ?? "The job status could not be loaded.");
  }

  return (await res.json()) as ResearchJobStatus;
}

export async function runResearch(topic: string, signal?: AbortSignal, documents: UploadedDocument[] = []): Promise<ResearchResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 180_000);
  signal?.addEventListener("abort", () => controller.abort());

  try {
    const baseUrl = await resolveApiBaseUrl();
    const res = await fetch(`${baseUrl}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, documents }),
      signal: controller.signal,
    });

    if (res.ok) return (await res.json()) as ResearchResult;

    if (res.status === 502) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(body.message ?? "An agent step failed.", body.step);
    }
    if (res.status === 422) throw new ApiError("That topic could not be processed.");
    throw new ApiError(`The API returned an error (${res.status}).`);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (signal?.aborted) throw new ApiError("Research cancelled.");
    if (controller.signal.aborted) throw new ApiError("The request timed out after 3 minutes.");
    throw new ApiError("Cannot reach the AgentLab API.");
  } finally {
    clearTimeout(timer);
  }
}
