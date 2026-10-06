"use client";

import { motion } from "motion/react";
import { Check, Circle, Minus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { STAGES, type Phase, type Stage } from "@/lib/types";

type State = "complete" | "queued" | "failed" | "not-run";

function stateOf(phase: Phase, failed: Stage | null, currentStep: Stage | null, completedSteps: Stage[], index: number): State {
  const stage = STAGES[index]?.key ?? null;
  if (phase === "done") return "complete";

  if (failed && failed === stage) return "failed";
  if (completedSteps.includes(stage as Stage)) return "complete";
  if (currentStep === stage) return "queued";

  return "not-run";
}

export function PipelineTracker({ phase, failed, currentStep, completedSteps }: { phase: Phase; failed: Stage | null; currentStep: Stage | null; completedSteps: Stage[] }) {
  const activeStage = currentStep ?? (phase === "running" ? STAGES[0].key : null);

  return (
    <section aria-label="Pipeline progress" className="print:hidden">
      <div className="mb-4 flex items-center justify-between gap-3 rounded-2xl border border-rule bg-paper/80 px-4 py-3 shadow-[var(--shadow-soft)]">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted">Live status</div>
          <div className="mt-1 font-serif text-xl text-ink">
            {phase === "running" ? `Processing: ${STAGES.find((stage) => stage.key === activeStage)?.label ?? "Research"}` : phase === "error" ? "Research paused" : "Research complete"}
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-rule bg-surface px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
          <span className={cn("inline-flex size-2 rounded-full", phase === "running" ? "bg-accent" : phase === "error" ? "bg-amber-500" : "bg-emerald-500")} aria-hidden />
          {phase === "running" ? "In progress" : phase === "error" ? "Needs attention" : "Done"}
        </div>
      </div>

      <div className="h-px w-full overflow-hidden bg-rule">
        {phase === "running" && (
          <motion.div
            className="h-px w-1/3 bg-accent"
            animate={{ x: ["-100%", "300%"] }}
            transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
          />
        )}
      </div>

      <ol>
        {STAGES.map((stage, i) => {
          const state = stateOf(phase, failed, currentStep, completedSteps, i);
          const isActive = currentStep === stage.key;
          return (
            <li
              key={stage.key}
              className={cn(
                "grid grid-cols-[28px_1fr_auto] items-baseline gap-3 border-b border-rule py-3 sm:grid-cols-[28px_130px_1fr_auto]",
                isActive && phase === "running" && "rounded-xl border border-accent/30 bg-accent/[0.04] px-2"
              )}
            >
              <span className="font-mono text-xs text-muted">{String(i + 1).padStart(2, "0")}</span>
              <span className={cn("font-serif text-lg", isActive && phase === "running" && "text-ink")}>{stage.label}</span>
              <span className="hidden text-muted sm:block">{stage.note}</span>
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-wide",
                  state === "failed" ? "text-accent" : state === "complete" ? "text-ink" : state === "queued" ? "text-accent" : "text-muted"
                )}
              >
                {state === "complete" && <Check className="size-3.5" aria-hidden />}
                {state === "failed" && <X className="size-3.5" aria-hidden />}
                {state === "queued" && <Circle className="size-3 animate-pulse motion-reduce:animate-none" aria-hidden />}
                {state === "not-run" && <Minus className="size-3.5" aria-hidden />}
                {state === "complete" ? "complete" : state === "queued" ? "processing" : state === "failed" ? "failed" : "waiting"}
              </span>
            </li>
          );
        })}
      </ol>

    </section>
  );
}
