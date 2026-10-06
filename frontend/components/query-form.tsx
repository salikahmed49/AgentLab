"use client";

import { ArrowRight, Clock, Search, Upload, X } from "lucide-react";
import { useRef } from "react";
import type { UploadedDocument } from "@/lib/types";

type Props = {
  topic: string;
  running: boolean;
  recent: string[];
  documents: UploadedDocument[];
  onTopic: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  onUploadFiles: (files: File[]) => Promise<void> | void;
  onClearDocuments: () => void;
};

const EXAMPLES = [
  "Solid-state batteries",
  "Microplastics and human health",
  "How CRISPR therapies are regulated",
];

const chip =
  "rounded-full border border-rule px-3 py-1 text-sm text-muted transition-colors hover:border-ink hover:text-ink disabled:opacity-50";

export function QueryForm({ topic, running, recent, documents, onTopic, onSubmit, onCancel, onUploadFiles, onClearDocuments }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <section className="pb-10 pt-10 print:hidden">
      <div className="overflow-hidden rounded-[28px] border border-rule/80 bg-surface/90 p-5 shadow-[var(--shadow-soft)] backdrop-blur-sm sm:p-6 lg:p-8">
        <div className="max-w-[54rem]">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-rule bg-paper/80 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
              <span className="inline-block size-2 rounded-full bg-accent" aria-hidden />
              AI research engine
            </div>
            <h1 className="font-serif text-4xl font-semibold leading-tight tracking-tight sm:text-5xl lg:text-[3.4rem]">
              Research the web with source-checked reasoning.
            </h1>
        </div>

        <p className="mt-5 max-w-[60ch] text-base leading-7 text-muted">
          AgentLab gathers the best sources, analyses the evidence, checks each claim against the material, and turns it into a readable report.
          Most runs finish in 30–90 seconds.
        </p>

        <form
          className="mt-8"
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit();
          }}
        >
          <div className="mb-2 flex items-center justify-between gap-3">
            <label htmlFor="topic" className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
              Research topic
            </label>
            <button
              type="button"
              disabled={running}
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-full border border-rule bg-surface/80 px-2.5 py-1.5 text-[11px] font-medium text-muted transition hover:border-ink hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Upload className="size-3.5" aria-hidden /> Add doc
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".txt,.md,.csv,.json,.pdf"
              multiple
              className="hidden"
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                if (files.length > 0) {
                  void onUploadFiles(files);
                }
                event.target.value = "";
              }}
            />
          </div>

          <div className="flex flex-col gap-2 rounded-2xl border border-ink/15 bg-paper/80 p-2 shadow-inner shadow-black/5 transition-all duration-200 focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15 sm:flex-row sm:items-center">
            <Search className="ml-2 hidden size-5 shrink-0 text-muted sm:block" aria-hidden />
            <input
              id="topic"
              value={topic}
              onChange={(e) => onTopic(e.target.value)}
              placeholder="Type a topic, for example: Solid-state batteries"
              disabled={running}
              autoComplete="off"
              maxLength={200}
              className="min-w-0 flex-1 bg-transparent px-2 py-3 font-serif text-xl text-ink outline-none placeholder:text-muted/70 disabled:opacity-60"
            />
            {running ? (
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-ink/20 bg-transparent px-5 py-3 text-sm font-medium text-ink transition-colors hover:bg-ink hover:text-paper"
              >
                <X className="size-4" aria-hidden /> Cancel
              </button>
            ) : (
              <button
                type="submit"
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-medium text-paper transition hover:bg-[var(--accent-strong)]"
              >
                Run research <ArrowRight className="size-4" aria-hidden />
              </button>
            )}
          </div>

          {documents.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {documents.map((document) => (
                <div key={document.name} className="rounded-full border border-rule bg-paper/80 px-3 py-1 text-xs text-muted">
                  {document.name}
                </div>
              ))}
              <button type="button" onClick={onClearDocuments} className="text-xs text-muted underline-offset-4 hover:underline">
                Clear all
              </button>
            </div>
          )}
        </form>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="mr-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted">Try</span>
          {EXAMPLES.map((example) => (
            <button key={example} type="button" disabled={running} className={chip} onClick={() => onTopic(example)}>
              {example}
            </button>
          ))}
        </div>

        {recent.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="mr-1 inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
              <Clock className="size-3" aria-hidden /> Recent
            </span>
            {recent.map((item) => (
              <button key={item} type="button" disabled={running} className={chip} onClick={() => onTopic(item)}>
                {item}
              </button>
            ))}
          </div>
        )}
      </div>

    </section>
  );
}
