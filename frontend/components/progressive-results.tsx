import { ExternalLink } from "lucide-react";
import { MarkdownView } from "@/components/markdown-view";
import type { ResearchResult } from "@/lib/types";

export function ProgressiveResults({ result }: { result: ResearchResult }) {
  const sections = [
    ["Research", result.research],
    ["Analysis", result.analysis],
    ["Verification", result.verification],
    ["Report", result.report],
  ] as const;

  const hasContent =
    sections.some(([, content]) => Boolean(content)) ||
    result.sources.length > 0 ||
    Boolean(result.citations?.length) ||
    Boolean(result.follow_up_questions?.length);

  if (!hasContent) return null;

  return (
    <section aria-label="Completed research sections" className="mt-8 space-y-5">
      <h2 className="font-serif text-2xl text-ink">{result.topic}</h2>

      {sections.map(([title, content]) =>
        content ? (
          <article
            key={title}
            aria-live="polite"
            className="rounded-2xl border border-rule bg-surface/90 p-5 shadow-[var(--shadow-soft)]"
          >
            <h3 className="mb-3 font-serif text-xl text-ink">{title}</h3>
            <MarkdownView text={content} labels={title === "Verification"} />
          </article>
        ) : null
      )}

      {result.sources.length > 0 && (
        <article
          aria-live="polite"
          className="rounded-2xl border border-rule bg-surface/90 p-5 shadow-[var(--shadow-soft)]"
        >
          <h3 className="mb-3 font-serif text-xl text-ink">Sources</h3>
          <ol className="space-y-3">
            {result.sources.map((source, index) => (
              <li key={`${source.url}-${index}`} className="text-sm leading-6">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-ink underline underline-offset-4 hover:text-accent"
                >
                  {source.title}
                  <ExternalLink className="size-3.5" aria-hidden />
                </a>
                <p className="mt-1 text-muted">{source.content}</p>
              </li>
            ))}
          </ol>
        </article>
      )}

      {Boolean(result.citations?.length) && (
        <article
          aria-live="polite"
          className="rounded-2xl border border-rule bg-surface/90 p-5 shadow-[var(--shadow-soft)]"
        >
          <h3 className="mb-3 font-serif text-xl text-ink">Evidence citations</h3>
          <ol className="space-y-4">
            {result.citations?.map((citation, index) => (
              <li key={`${citation.source_url}-${index}`} className="text-sm leading-6">
                <p className="font-medium text-ink">{citation.claim}</p>
                <blockquote className="mt-1 border-l-2 border-rule pl-3 text-muted">
                  “{citation.quote}”
                </blockquote>
                <a
                  href={citation.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1.5 text-ink underline underline-offset-4 hover:text-accent"
                >
                  {citation.source_title}
                  <ExternalLink className="size-3.5" aria-hidden />
                </a>
              </li>
            ))}
          </ol>
        </article>
      )}

      {Boolean(result.follow_up_questions?.length) && (
        <article
          aria-live="polite"
          className="rounded-2xl border border-rule bg-surface/90 p-5 shadow-[var(--shadow-soft)]"
        >
          <h3 className="mb-3 font-serif text-xl text-ink">Suggested next questions</h3>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-muted">
            {result.follow_up_questions?.map((question, index) => (
              <li key={`${question}-${index}`}>{question}</li>
            ))}
          </ul>
        </article>
      )}
    </section>
  );
}
