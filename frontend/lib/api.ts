import type { ResearchResult, Stage, UploadedDocument } from "./types";

const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "");
const API_URL_CANDIDATES = configuredApiUrl
  ? [configuredApiUrl]
  : process.env.NODE_ENV === "development"
    ? ["http://localhost:8001", "http://localhost:8000"]
    : [];

async function resolveApiBaseUrl(): Promise<string> {
  const uniqueCandidates = [...new Set(API_URL_CANDIDATES)];
  if (uniqueCandidates.length === 0) {
    throw new ApiError(
      "The backend URL is not configured. Set NEXT_PUBLIC_API_URL in the Vercel environment and redeploy."
    );
  }

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

  throw new ApiError(
    `Cannot reach the backend at ${uniqueCandidates[0]}. Check NEXT_PUBLIC_API_URL, Render health, and the backend CORS_ORIGINS setting.`
  );
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

export type ResearchStreamEvent =
  | { event: "progress"; data: { step: Stage; state: "processing" | "completed" | "failed" } }
  | { event: "partial_result"; data: Partial<ResearchResult> }
  | { event: "report_section"; data: { index: number; section: string; text: string } }
  | { event: "complete"; data: ResearchResult }
  | { event: "error"; data: { step: Stage | null; message: string } };

const stages: Stage[] = [
  "research",
  "analysis",
  "verification",
  "report",
  "citation_linking",
  "follow_up_questions",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStage(value: unknown): value is Stage {
  return typeof value === "string" && stages.some((stage) => stage === value);
}

function isProgressState(value: unknown): value is "processing" | "completed" | "failed" {
  return value === "processing" || value === "completed" || value === "failed";
}

function isSource(value: unknown): value is ResearchResult["sources"][number] {
  return (
    isRecord(value) &&
    typeof value.title === "string" &&
    typeof value.url === "string" &&
    typeof value.content === "string" &&
    typeof value.score === "number"
  );
}

function isDocument(value: unknown): value is ResearchResult["documents"][number] {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.content === "string" &&
    typeof value.size === "number" &&
    typeof value.type === "string"
  );
}

function isCitation(
  value: unknown,
): value is NonNullable<ResearchResult["citations"]>[number] {
  return (
    isRecord(value) &&
    typeof value.claim === "string" &&
    typeof value.source_title === "string" &&
    typeof value.source_url === "string" &&
    typeof value.quote === "string"
  );
}

function isResearchResult(value: unknown): value is ResearchResult {
  return (
    isRecord(value) &&
    typeof value.topic === "string" &&
    typeof value.status === "string" &&
    typeof value.research === "string" &&
    typeof value.analysis === "string" &&
    typeof value.verification === "string" &&
    typeof value.report === "string" &&
    Array.isArray(value.sources) &&
    Array.isArray(value.documents)
  );
}

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

export async function runResearchStream(
  topic: string,
  signal: AbortSignal,
  documents: UploadedDocument[] = [],
  onEvent: (event: ResearchStreamEvent) => void,
): Promise<ResearchResult> {
  const baseUrl = await resolveApiBaseUrl();
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/research/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ topic, documents }),
      signal,
    });
  } catch {
    if (signal.aborted) throw new ApiError("Research cancelled.");
    throw new ApiError("Cannot reach the AgentLab API.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(body.detail ?? body.message ?? `The API returned an error (${response.status}).`, body.step);
  }
  if (!response.body) {
    throw new ApiError("The backend did not provide a research event stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (frame: string): ResearchResult | null => {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) return null;

    let payload: unknown;
    try {
      payload = JSON.parse(dataLines.join("\n"));
    } catch {
      throw new ApiError("The backend sent an invalid research event.");
    }

    if (!isRecord(payload)) {
      throw new ApiError("The backend sent an invalid research event.");
    }

    let streamEvent: ResearchStreamEvent;
    if (eventName === "progress") {
      if (
        !isStage(payload.step) ||
        !isProgressState(payload.state)
      ) {
        throw new ApiError("The backend sent an invalid progress event.");
      }
      streamEvent = {
        event: "progress",
        data: {
          step: payload.step,
          state: payload.state,
        },
      };
    } else if (eventName === "partial_result") {
      const partial: Partial<ResearchResult> = {};
      for (const field of ["topic", "status", "research", "analysis", "verification", "report"] as const) {
        if (typeof payload[field] === "string") partial[field] = payload[field];
      }
      if (Array.isArray(payload.sources) && payload.sources.every(isSource)) {
        partial.sources = payload.sources;
      }
      if (Array.isArray(payload.documents) && payload.documents.every(isDocument)) {
        partial.documents = payload.documents;
      }
      if (Array.isArray(payload.citations) && payload.citations.every(isCitation)) {
        partial.citations = payload.citations;
      }
      if (Array.isArray(payload.follow_up_questions)) {
        partial.follow_up_questions = payload.follow_up_questions.filter(
          (question): question is string => typeof question === "string",
        );
      }
      streamEvent = { event: "partial_result", data: partial };
    } else if (eventName === "report_section") {
      if (
        typeof payload.index !== "number" ||
        !Number.isInteger(payload.index) ||
        typeof payload.section !== "string" ||
        typeof payload.text !== "string"
      ) {
        throw new ApiError("The backend sent an invalid report section.");
      }
      streamEvent = {
        event: "report_section",
        data: { index: payload.index, section: payload.section, text: payload.text },
      };
    } else if (eventName === "complete") {
      if (!isResearchResult(payload)) {
        throw new ApiError("The backend sent an invalid final research result.");
      }
      streamEvent = { event: "complete", data: payload };
    } else if (eventName === "error") {
      if (
        typeof payload.message !== "string" ||
        (payload.step !== null && !isStage(payload.step))
      ) {
        throw new ApiError("The backend sent an invalid research error event.");
      }
      throw new ApiError(payload.message, payload.step ?? undefined);
    } else {
      throw new ApiError(`The backend sent an unknown research event (${eventName}).`);
    }

    onEvent(streamEvent);
    return streamEvent.event === "complete" ? streamEvent.data : null;
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separator = buffer.search(/\r?\n\r?\n/);
      while (separator !== -1) {
        const frame = buffer.slice(0, separator);
        const separatorMatch = buffer.slice(separator).match(/^\r?\n\r?\n/);
        buffer = buffer.slice(separator + (separatorMatch?.[0].length ?? 2));
        const result = dispatch(frame);
        if (result) return result;
        separator = buffer.search(/\r?\n\r?\n/);
      }
    }
    if (buffer.trim()) {
      const result = dispatch(buffer);
      if (result) return result;
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (signal.aborted) throw new ApiError("Research cancelled.");
    throw new ApiError("The research event stream was interrupted.");
  } finally {
    reader.releaseLock();
  }

  throw new ApiError("The research stream ended before completing the report.");
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
