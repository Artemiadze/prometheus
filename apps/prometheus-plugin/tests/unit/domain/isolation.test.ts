import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const domainRoot = join(dirname(fileURLToPath(import.meta.url)), "../../../src/domain");

function collectTsFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      out.push(...collectTsFiles(full));
    } else if (name.endsWith(".ts")) {
      out.push(full);
    }
  }
  return out;
}

describe("domain layer isolation (PLG-80)", () => {
  it("does not import obsidian or perform network I/O modules", () => {
    const files = collectTsFiles(domainRoot);
    expect(files.length).toBeGreaterThan(0);
    for (const file of files) {
      const source = readFileSync(file, "utf8");
      expect(source, file).not.toMatch(/from ["']obsidian["']/);
      expect(source, file).not.toMatch(/from ["']node:https?["']/);
      expect(source, file).not.toMatch(/\bfetch\s*\(/);
    }
  });
});
