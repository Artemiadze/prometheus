import { createHash } from "node:crypto";

/** Normalize transport-level text differences before hashing (runtime PRM-9). */
export function normalizeContent(text: string): string {
  const withoutBom = text.startsWith("\ufeff") ? text.slice(1) : text;
  const normalized = withoutBom.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  return normalized
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/g, ""))
    .join("\n");
}

/** SHA-256 of normalized Markdown content — must match runtime compute_content_hash. */
export function computeContentHash(text: string): string {
  return createHash("sha256").update(normalizeContent(text), "utf8").digest("hex");
}
