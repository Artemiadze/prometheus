import { describe, expect, it } from "vitest";

import type { JobInfo } from "../../../src/application/dto/rag";
import type { Clock } from "../../../src/application/ports/Clock";
import { JobTracker } from "../../../src/application/services/JobTracker";
import { VaultId } from "../../../src/domain/value-objects/VaultId";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";

describe("JobTracker", () => {
  it("uses bounded adaptive polling and publishes progress", async () => {
    const jobs: JobInfo[] = [
      job("pending", 0),
      job("running", 0),
      job("running", 0),
      job("running", 0),
      job("running", 0.5),
      job("completed", 1),
    ];
    const rag = new FakeRagGateway();
    rag.getJob = async () => jobs.shift() ?? job("completed", 1);
    const clock = new RecordingClock();
    const updates: number[] = [];
    const tracker = new JobTracker(rag, clock, {
      initialPollIntervalMs: 100,
      maxPollIntervalMs: 400,
      backoffFactor: 2,
    });

    const result = await tracker.watch("job-a1", (update) => {
      updates.push(update.progress);
    });

    expect(result.status).toBe("completed");
    expect(clock.sleeps).toEqual([100, 100, 200, 400, 100]);
    expect(updates).toEqual([0, 0, 0, 0, 0.5, 1]);
  });

  it("stops an active sleep when the panel abort signal closes", async () => {
    const rag = new FakeRagGateway();
    rag.holdJobsPending = true;
    const started = await rag.reindex(VaultId.create("vault-a1"), []);
    const clock = new FakeClock();
    const tracker = new JobTracker(rag, clock, { initialPollIntervalMs: 100 });
    const controller = new AbortController();

    const watching = tracker.watch(started.jobId, undefined, controller.signal);
    await Promise.resolve();
    controller.abort();
    await expect(watching).rejects.toMatchObject({ name: "AbortError" });
  });
});

class RecordingClock implements Clock {
  readonly sleeps: number[] = [];

  now(): Date {
    return new Date(0);
  }

  async sleep(ms: number, signal?: AbortSignal): Promise<void> {
    if (signal?.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    this.sleeps.push(ms);
  }
}

function job(status: JobInfo["status"], progress: number): JobInfo {
  return { jobId: "job-a1", status, progress, error: null };
}
