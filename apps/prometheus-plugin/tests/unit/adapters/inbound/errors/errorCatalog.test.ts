import { describe, expect, it } from "vitest";

import {
  ERROR_CATALOG,
  formatPresentedMessage,
} from "../../../../../src/adapters/inbound/obsidian/errors/errorCatalog";
import type { PrometheusPluginErrorCode } from "../../../../../src/domain/errors";

const ALL_CODES = Object.keys(ERROR_CATALOG) as PrometheusPluginErrorCode[];

describe("errorCatalog", () => {
  it("has a non-empty cause and nextStep for every error code", () => {
    expect(ALL_CODES.length).toBeGreaterThan(20);
    for (const code of ALL_CODES) {
      const entry = ERROR_CATALOG[code];
      expect(entry.cause.trim().length, code).toBeGreaterThan(0);
      expect(entry.nextStep.trim().length, code).toBeGreaterThan(0);
      expect(formatPresentedMessage(entry)).toContain(entry.cause);
      expect(formatPresentedMessage(entry)).toContain(entry.nextStep);
    }
  });

  it("covers runtime-not-installed with a cloud-free next step", () => {
    const entry = ERROR_CATALOG.RUNTIME_NOT_INSTALLED;
    expect(entry.cause.toLowerCase()).toContain("not installed");
    expect(entry.nextStep.toLowerCase()).toContain("no cloud");
  });
});
