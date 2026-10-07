import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function slugify(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export function normalizeGeneratedMarkup(text: string) {
  return text
    .replace(/&lt;(\/?[a-z][a-z0-9:-]*(?:\s+[^&<>]*?)?\/?)&gt;/gi, "<$1>")
    .replace(/<\/?br\s*\/?\s*>/gi, "\n\n")
    .replace(/<\/(?:p|div|section|article|h[1-6]|li|ul|ol|tr|table|blockquote)>/gi, "\n")
    .replace(/<(?:li)\b[^>]*>/gi, "\n- ")
    .replace(/<\/?(?:p|div|section|article|h[1-6]|ul|ol|tr|table|blockquote)\b[^>]*>/gi, "\n")
    .replace(/<\/?[a-z][a-z0-9:-]*(?:\s+[^<>]*?)?\s*\/?>/gi, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function hostOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function headings(markdown: string): { id: string; text: string }[] {
  return markdown
    .split("\n")
    .filter((line) => line.startsWith("## "))
    .map((line) => {
      const text = line.replace(/^##\s+/, "").replace(/[*_`]/g, "").trim();
      return { id: slugify(text), text };
    });
}
