import { describe, expect, it } from "vitest";

import { ActiveJobRegistry } from "../../../src/application/services/ActiveJobRegistry";

describe("ActiveJobRegistry", () => {
  it("stores and clears the active job", () => {
    const registry = new ActiveJobRegistry();
    expect(registry.get()).toBeNull();
    const job = { jobId: "job-1", status: "running" as const, progress: 0.5, error: null };
    registry.set(job);
    expect(registry.get()).toEqual(job);
    registry.clear();
    expect(registry.get()).toBeNull();
  });
});
