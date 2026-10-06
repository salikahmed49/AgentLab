"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, Copy, Download, ExternalLink, Printer } from "lucide-react";
import { toast } from "sonner";
import { MarkdownView } from "@/components/markdown-view";
import type { ResearchResult } from "@/lib/types";
import { cn, headings, hostOf, slugify } from "@/lib/utils";

const TABS = [
  "Report",
  "Research",
  "Analysis",
  "Verification",
  "Sources",
  "Citations",
  "Next questions",
] as const;
type Tab = (typeof TABS)[number];

const action =
  "inline-flex items-center gap-1.5 rounded-md border border-rule px-3 py-1.5 text-sm transition-colors hover:border-ink";

export function Results({ result }: { result: ResearchResult }) {
  const [tab, setTab] = useState<Tab>("Report");
  const [copied, setCopied] = useState(false);
  const toc = headings(result.report);

  function onKey(e: React.KeyboardEvent) {
    const i = TABS.indexOf(tab);
    let next = i;
    if (e.key === "ArrowRight") next = (i + 1) % TABS.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + TABS.length) % TABS.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = TABS.length - 1;
    else return;
    e.preventDefault();
    setTab(TABS[next]);
    document.getElementById(`tab-${TABS[next]}`)?.focus();
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(result.report);
      setCopied(true);
      toast.success("Markdown copied");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Could not copy to the clipboard");
    }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([result.report], { type: "text/markdown" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${slugify(result.topic).slice(0, 60) || "report"}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="mt-10 print:mt-0">
      <div className="overflow-hidden rounded-[28px] border border-rule/80 bg-surface/90 p-3 shadow-[var(--shadow-soft)] backdrop-blur-sm print:shadow-none print:bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-2 pb-3 pt-1 print:hidden">
          <div role="tablist" aria-label="Result sections" onKeyDown={onKey} className="-mb-px flex gap-2 overflow-x-auto">
            {TABS.map((t) => (
              <button
                key={t}
                role="tab"
                id={`tab-${t}`}
                aria-selected={tab === t}
                aria-controls="panel"
                tabIndex={tab === t ? 0 : -1}
                onClick={() => setTab(t)}
                className={cn(
                  "whitespace-nowrap rounded-t-xl border-b-2 px-3 py-2.5 text-sm font-medium transition-all",
                  tab === t
                    ? "border-accent bg-paper text-ink"
                    : "border-transparent bg-transparent text-muted hover:border-rule hover:text-ink"
                )}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 pb-1">
            <button type="button" className={action} onClick={copy}>
              {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />} Copy
            </button>
            <button type="button" className={action} onClick={download}>
              <Download className="size-4" aria-hidden /> .md
            </button>
            <button type="button" className={action} onClick={() => window.print()}>
              <Printer className="size-4" aria-hidden /> Print
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-8 px-2 pb-2 lg:grid-cols-[minmax(0,1fr)_240px]">
          <div id="panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="min-w-0">
            <AnimatePresence mode="wait">
              <motion.div
                key={tab}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="max-w-[68ch]"
              >
                {tab === "Report" && <MarkdownView text={result.report} />}
                {tab === "Research" && <MarkdownView text={result.research} />}
                {tab === "Analysis" && <MarkdownView text={result.analysis} />}
                {tab === "Verification" && <MarkdownView text={result.verification} labels />}
                {tab === "Sources" && (
                  <ol className="space-y-4 pl-0">
                    {result.sources.map((source, i) => (
                      <li key={source.url + i} className="rounded-2xl border border-rule bg-paper/70 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <a
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 font-serif text-lg text-ink underline underline-offset-4 hover:text-accent"
                            >
                              {source.title} <ExternalLink className="size-3.5 shrink-0" aria-hidden />
                            </a>
                            <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                              {hostOf(source.url)} • Relevance {source.score.toFixed(2)}
                            </div>
                          </div>
                          <span className="shrink-0 rounded-full border border-rule bg-surface px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                            #{i + 1}
                          </span>
                        </div>
                        <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted">{source.content}</p>
                      </li>
                    ))}
                  </ol>
                )}
                {tab === "Citations" && (
                  <ol className="space-y-5 pl-0">
                    {(result.citations ?? []).map((citation, i) => (
                      <li key={`${citation.source_url}-${i}`} className="rounded-2xl border border-rule bg-paper/70 p-4">
                        <p className="font-medium text-ink">{citation.claim}</p>
                        <blockquote className="mt-2 border-l-2 border-rule pl-3 text-sm leading-6 text-muted">
                          “{citation.quote}”
                        </blockquote>
                        <a
                          href={citation.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-2 inline-flex items-center gap-1.5 text-sm text-ink underline underline-offset-4 hover:text-accent"
                        >
                          {citation.source_title}
                          <ExternalLink className="size-3.5" aria-hidden />
                        </a>
                      </li>
                    ))}
                    {(result.citations ?? []).length === 0 && (
                      <p className="text-sm text-muted">No evidence citations were produced.</p>
                    )}
                  </ol>
                )}
                {tab === "Next questions" && (
                  <ol className="list-decimal space-y-3 pl-5 text-sm leading-6 text-muted">
                    {(result.follow_up_questions ?? []).map((question, i) => (
                      <li key={`${question}-${i}`}>{question}</li>
                    ))}
                    {(result.follow_up_questions ?? []).length === 0 && (
                      <p className="list-none text-muted">No follow-up questions were produced.</p>
                    )}
                  </ol>
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          <aside className="hidden print:hidden lg:block">
            <div className="sticky top-6 space-y-5 text-sm">
              {tab === "Report" && toc.length > 0 && (
                <nav aria-label="Table of contents" className="rounded-2xl border border-rule bg-paper/70 p-4">
                  <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">On this page</p>
                  <ul className="mt-3 space-y-2">
                    {toc.map((h) => (
                      <li key={h.id}>
                        <a
                          href={`#${h.id}`}
                          className="block rounded-md px-2 py-1.5 text-muted transition-colors hover:bg-surface hover:text-ink"
                        >
                          {h.text}
                        </a>
                      </li>
                    ))}
                  </ul>
                </nav>
              )}

              <dl className="space-y-3 rounded-2xl border border-rule bg-paper/70 p-4 text-xs text-muted">
                <div>
                  <dt className="font-mono uppercase tracking-[0.18em]">Topic</dt>
                  <dd className="mt-1 text-sm text-ink">{result.topic}</dd>
                </div>
                <div>
                  <dt className="font-mono uppercase tracking-[0.18em]">Sources</dt>
                  <dd className="mt-1 text-sm text-ink">{result.sources.length}</dd>
                </div>
              </dl>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
