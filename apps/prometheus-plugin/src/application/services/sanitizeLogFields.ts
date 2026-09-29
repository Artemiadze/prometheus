import type { LogFields } from "../ports/Logger";

const BLOCKED_KEY = /token|password|secret|content|text|query|note/i;
const MAX_STRING_LENGTH = 64;

/**
 * Drop fields that could carry user content or credentials.
 */
export function sanitizeLogFields(fields: LogFields | undefined): LogFields {
  if (!fields) {
    return {};
  }
  const result: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(fields)) {
    if (BLOCKED_KEY.test(key)) {
      continue;
    }
    if (typeof value === "string") {
      if (value.length > MAX_STRING_LENGTH || value.includes("\n") || value.includes("\r")) {
        continue;
      }
      result[key] = value;
      continue;
    }
    if (typeof value === "number" || typeof value === "boolean") {
      result[key] = value;
    }
  }
  return result;
}
