export type Source = { title: string; url: string; content: string; score: number };

export type UploadedDocument = {
  name: string;
  content: string;
  size: number;
  type: string;
};

export type EvidenceCitation = {
  claim: string;
  source_title: string;
  source_url: string;
  quote: string;
};

export type ResearchResult = {
  topic: string;
  status: string;
  research: string;
  analysis: string;
  verification: string;
  report: string;
  sources: Source[];
  documents: UploadedDocument[];
  citations?: EvidenceCitation[];
  follow_up_questions?: string[];
};

export type Phase = "idle" | "running" | "done" | "error";
export type Stage =
  | "research"
  | "analysis"
  | "verification"
  | "report"
  | "citation_linking"
  | "follow_up_questions";

export const STAGES: { key: Stage; label: string; note: string }[] = [
  { key: "research", label: "Research", note: "Searches the web and summarises what it finds" },
  { key: "analysis", label: "Analysis", note: "Looks for patterns, gaps and disagreements" },
  { key: "verification", label: "Verification", note: "Checks each claim against the sources" },
  { key: "report", label: "Report", note: "Writes the final report" },
  { key: "citation_linking", label: "Citations", note: "Links report claims to source evidence" },
  { key: "follow_up_questions", label: "Next questions", note: "Suggests useful directions for further research" },
];
