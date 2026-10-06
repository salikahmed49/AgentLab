const KEY = "agentlab:recent";

export function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string").slice(0, 5) : [];
  } catch {
    return [];
  }
}

export function saveRecent(topic: string): string[] {
  const next = [topic, ...loadRecent().filter((t) => t.toLowerCase() !== topic.toLowerCase())].slice(0, 5);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage unavailable: ignore
  }
  return next;
}
