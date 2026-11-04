import { describe, expect, it, vi } from "vitest";

import { DocumentSyncState } from "../../../src/application/services/DocumentSyncState";
import { DocumentId } from "../../../src/domain/value-objects/DocumentId";
import { NotePath } from "../../../src/domain/value-objects/NotePath";

describe("DocumentSyncState.nextRevision", () => {
  it("returns a monotonic wall-clock revision when the ledger is empty", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-15T12:00:00.000Z"));
    const syncState = new DocumentSyncState();
    const path = NotePath.create("a.md");

    const revision = syncState.nextRevision(path);
    expect(revision).toBe(Date.now());
    expect(revision).toBeGreaterThan(1);

    vi.useRealTimers();
  });

  it("stays strictly greater than a prior stored revision", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-15T12:00:00.000Z"));
    const syncState = new DocumentSyncState();
    const path = NotePath.create("a.md");
    const now = Date.now();
    syncState.upsert({
      documentId: DocumentId.fromNotePath(path),
      path,
      contentHash: "a".repeat(64),
      revision: now + 10_000,
    });

    const next = syncState.nextRevision(path);
    expect(next).toBe(now + 10_001);

    vi.useRealTimers();
  });
});
