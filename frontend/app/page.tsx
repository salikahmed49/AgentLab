"use client";

import { useEffect, useRef, useState } from "react";
import { MotionConfig } from "motion/react";
import Image from "next/image";
import { AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { PipelineTracker } from "@/components/pipeline-tracker";
import { QueryForm } from "@/components/query-form";
import { Results } from "@/components/results";
import { ProgressiveResults } from "@/components/progressive-results";
import { ApiError, runResearchStream, uploadDocuments } from "@/lib/api";
import { loadRecent, saveRecent } from "@/lib/history";
import type { Phase, ResearchResult, Stage, UploadedDocument } from "@/lib/types";

function emptyResult(topic: string): ResearchResult {
  return {
    topic,
    status: "running",
    research: "",
    analysis: "",
    verification: "",
    report: "",
    sources: [],
    documents: [],
    citations: [],
    follow_up_questions: [],
  };
}

function formatStreamedReport(
  topic: string,
  sections: Record<number, { section: string; text: string }>,
): string {
  const content = Object.keys(sections)
    .map(Number)
    .sort((left, right) => left - right)
    .map((index) => `## ${sections[index].section}\n\n${sections[index].text}`)
    .join("\n\n");
  return `# ${topic}${content ? `\n\n${content}` : ""}`;
}

function getUserFriendlyError(message: string): string {
  const normalized = message.toLowerCase();

  if (normalized.includes("groq_api_key") || normalized.includes("api key is not configured")) {
    return "The AI model is not configured for this environment. Please check the backend API keys before retrying.";
  }

  if (normalized.includes("tavily_api_key") || normalized.includes("tavily")) {
    return "The search provider is not configured for this environment. Please check the backend settings before retrying.";
  }

  return message;
}

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof Error) return new ApiError(error.message);
  return new ApiError("Research could not be completed.");
}

export default function Home() {
  const [topic, setTopic] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [failed, setFailed] = useState<Stage | null>(null);
  const [currentStep, setCurrentStep] = useState<Stage | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Stage[]>([]);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [partialResult, setPartialResult] = useState<ResearchResult | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
      Promise.resolve().then(() => {
        setRecent(loadRecent());
      });
  }, []);

  async function submit() {
    const clean = topic.trim();

    if (clean.length < 3 || clean.length > 200) {
      setError("Enter a topic between 3 and 200 characters.");
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    setPhase("running");
    setError("");
    setFailed(null);
    setCurrentStep(null);
    setCompletedSteps([]);
    setResult(null);
    setPartialResult(emptyResult(clean));

    try {
      let streamedSections: Record<number, { section: string; text: string }> = {};
      const completedResult = await runResearchStream(
        clean,
        controller.signal,
        documents,
        (event) => {
          if (event.event === "progress") {
            if (event.data.state === "processing") {
              setCurrentStep(event.data.step);
            } else if (event.data.state === "completed") {
              setCompletedSteps((current) =>
                current.includes(event.data.step) ? current : [...current, event.data.step]
              );
            } else {
              setFailed(event.data.step);
            }
          } else if (event.event === "partial_result") {
            setPartialResult((current) => ({
              ...emptyResult(clean),
              ...current,
              ...event.data,
            }));
          } else if (event.event === "report_section") {
            if (event.data.index < 0) {
              streamedSections = {};
              setPartialResult((current) => ({
                ...emptyResult(clean),
                ...current,
                report: event.data.text,
              }));
              return;
            }
            streamedSections[event.data.index] = {
              section: event.data.section,
              text: event.data.text,
            };
            const report = formatStreamedReport(clean, streamedSections);
            setPartialResult((current) => ({
              ...emptyResult(clean),
              ...current,
              report,
            }));
          }
        },
      );
      setResult(completedResult);
      setPartialResult(null);
      setPhase("done");
      setCurrentStep(null);
      setCompletedSteps((current) => {
        const finalSteps: Stage[] = [...current];
        for (const step of ["citation_linking", "follow_up_questions"] as const) {
          if (!finalSteps.includes(step)) finalSteps.push(step);
        }
        return finalSteps;
      });
      setRecent(saveRecent(clean));
      toast.success(documents.length > 0 ? "Report ready with uploaded documents" : "Report ready");
    } catch (err) {
      const apiError = toApiError(err);
      setError(getUserFriendlyError(apiError.message));
      setFailed(apiError.step ?? null);
      setPhase("error");
    } finally {
      abortRef.current = null;
    }
  }

  return (
    <MotionConfig reducedMotion="user">
      <main className="mx-auto max-w-5xl px-6 pb-24">
        <header className="flex items-center border-b border-rule py-5 print:hidden">
          <Image src="/agentlab-logo.svg" alt="AgentLab" width={276} height={63} priority className="h-10 w-auto sm:h-12" />
        </header>

        <QueryForm
          topic={topic}
          running={phase === "running"}
          recent={recent}
          documents={documents}
          onTopic={setTopic}
          onSubmit={submit}
          onCancel={() => abortRef.current?.abort()}
          onUploadFiles={async (files) => {
            try {
              const uploaded = await uploadDocuments(files);
              setDocuments((current) => [...current, ...uploaded]);
              toast.success(`${uploaded.length} document${uploaded.length === 1 ? "" : "s"} added`);
            } catch (err) {
              const apiError = toApiError(err);
              toast.error(apiError.message || "Could not upload the document.");
            }
          }}
          onClearDocuments={() => setDocuments([])}
        />

        {error && (
          <div role="alert" className="mb-8 overflow-hidden rounded-2xl border border-accent/30 bg-accent/[0.04] p-4 print:hidden">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-full bg-accent/10 p-1.5 text-accent">
                <AlertCircle className="size-4 shrink-0" aria-hidden />
              </div>
              <div className="flex-1">
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted">Research unavailable</p>
                <p className="mt-2 text-base text-ink">{getUserFriendlyError(error)}</p>
                {phase === "error" && (
                  <button type="button" className="mt-3 inline-flex items-center rounded-full border border-rule bg-paper px-3 py-1.5 text-sm text-ink transition hover:border-ink" onClick={submit}>
                    Try again
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {(phase === "running" || phase === "error") && (
          <PipelineTracker phase={phase} failed={failed} currentStep={currentStep} completedSteps={completedSteps} />
        )}

        {(phase === "running" || phase === "error") && partialResult && (
          <ProgressiveResults result={partialResult} />
        )}

        {phase === "done" && result && <Results result={result} />}
      </main>
    </MotionConfig>
  );
}
