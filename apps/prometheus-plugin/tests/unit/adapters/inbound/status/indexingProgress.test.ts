import { describe, expect, it } from "vitest";

import { estimateIndexingProgress } from "../../../../../src/adapters/inbound/obsidian/status/indexingProgress";

describe("estimateIndexingProgress", () => {
  it("reports scanning with zero progress", () => {
    const result = estimateIndexingProgress({
      phase: "scanning",
      processed: 0,
      total: 0,
      jobProgress: 0,
      elapsedMs: 0,
    });
    expect(result.processedDocs).toBe(0);
    expect(result.percent).toBe(0);
    expect(result.etaMs).toBeNull();
    expect(result.label).toBe("Scanning vault…");
  });

  it("uses exact upload counts", () => {
    const result = estimateIndexingProgress({
      phase: "uploading",
      processed: 40,
      total: 100,
      jobProgress: 0,
      elapsedMs: 10_000,
    });
    expect(result.processedDocs).toBe(40);
    expect(result.totalDocs).toBe(100);
    expect(result.percent).toBe(40);
    expect(result.etaMs).toBe(15_000);
    expect(result.label).toContain("40 / 100");
    expect(result.label).toContain("remaining");
  });

  it("approximates reconciling phase from job progress", () => {
    const result = estimateIndexingProgress({
      phase: "reconciling",
      processed: 100,
      total: 100,
      jobProgress: 0.25,
      elapsedMs: 20_000,
    });
    expect(result.processedDocs).toBe(25);
    expect(result.percent).toBe(25);
    expect(result.etaMs).toBe(60_000);
  });

  it("returns null ETA when progress is zero", () => {
    const result = estimateIndexingProgress({
      phase: "uploading",
      processed: 0,
      total: 50,
      jobProgress: 0,
      elapsedMs: 5_000,
    });
    expect(result.etaMs).toBeNull();
  });

  it("formats completed phase", () => {
    const result = estimateIndexingProgress({
      phase: "completed",
      processed: 12,
      total: 12,
      jobProgress: 1,
      elapsedMs: 1_000,
    });
    expect(result.percent).toBe(100);
    expect(result.label).toBe("Indexed 12 documents.");
  });
});
