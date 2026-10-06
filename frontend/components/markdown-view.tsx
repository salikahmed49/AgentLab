"use client";

import { Children, type ReactElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn, slugify } from "@/lib/utils";

const LABELS = /(PARTIALLY SUPPORTED|NOT SUPPORTED|CONFLICTING|SUPPORTED)/g;

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (node && typeof node === "object" && "props" in node) {
    return textOf((node as ReactElement<{ children?: ReactNode }>).props.children);
  }
  return "";
}

function decorate(children: ReactNode): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child !== "string") return child;
    return child.split(LABELS).map((part, i) => {
      if (i % 2 === 0) return part;
      const bad = part === "NOT SUPPORTED" || part === "CONFLICTING";
      return (
        <span
          key={i}
          className={cn(
            "mx-0.5 whitespace-nowrap rounded-sm border px-1.5 font-mono text-[11px] font-normal tracking-wide",
            bad ? "border-accent text-accent" : "border-muted text-ink"
          )}
        >
          {part}
        </span>
      );
    });
  });
}

function build(labels: boolean) {
  const wrap = (Tag: "p" | "li" | "td" | "strong") =>
    function Wrapped({ children }: { children?: ReactNode }) {
      return <Tag>{labels ? decorate(children) : children}</Tag>;
    };

  return {
    p: wrap("p"),
    li: wrap("li"),
    td: wrap("td"),
    strong: wrap("strong"),
    h2: ({ children }: { children?: ReactNode }) => <h2 id={slugify(textOf(children))}>{children}</h2>,
    a: ({ href, children }: { href?: string; children?: ReactNode }) => (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
  };
}

const PLAIN = build(false);
const LABELLED = build(true);

export function MarkdownView({ text, labels = false }: { text: string; labels?: boolean }) {
  return (
    <article className="report">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={labels ? LABELLED : PLAIN}>
        {text}
      </ReactMarkdown>
    </article>
  );
}
