import fs from "node:fs";
import postcss from "postcss";
import { transform } from "lightningcss";

const tw = await import("@tailwindcss/postcss");
const plugin = tw.default ?? tw;

const input = fs.readFileSync("app/globals.css", "utf8");
const result = await postcss([plugin()]).process(input, { from: "app/globals.css" });
fs.writeFileSync("tw-out.css", result.css);

const lines = result.css.split("\n");
console.log("Generated CSS lines:", lines.length);

const suspicious = lines
  .map((text, i) => [i + 1, text])
  .filter(([, text]) => /^\s*[>+~]/.test(text) || /[>+~]\s*\{\s*$/.test(text));

console.log("Suspicious selector lines:", suspicious.length);
suspicious.slice(0, 10).forEach(([n, text]) => console.log("  line " + n + ": " + text.trim()));

try {
  transform({ filename: "tw-out.css", code: Buffer.from(result.css), errorRecovery: false });
  console.log("PARSER RESULT: OK, lightningcss accepted the CSS");
} catch (e) {
  console.log("PARSER RESULT: FAILED -> " + e.message);
  const at = (e.loc && e.loc.line) || 1;
  console.log("--- generated CSS around line " + at + " ---");
  console.log(lines.slice(Math.max(0, at - 8), at + 6).join("\n"));
}
