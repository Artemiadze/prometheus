import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("prometheus-plugin foundation", () => {
  it("keeps package and manifest versions aligned", () => {
    const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
    const packageJson = JSON.parse(readFileSync(join(root, "package.json"), "utf8")) as {
      name: string;
      version: string;
    };
    const manifest = JSON.parse(readFileSync(join(root, "manifest.json"), "utf8")) as {
      version: string;
      isDesktopOnly: boolean;
    };

    expect(packageJson.name).toBe("prometheus-plugin");
    expect(packageJson.version).toBe(manifest.version);
    expect(manifest.isDesktopOnly).toBe(true);
  });
});
