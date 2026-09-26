import type { JobInfo, JobStatus } from "../dto/rag";
import type { Clock } from "../ports/Clock";
import type { RagGateway } from "../ports/RagGateway";

const TERMINAL: ReadonlySet<JobStatus> = new Set(["completed", "failed", "cancelled"]);

export type JobUpdateCallback = (job: JobInfo) => void;

export type JobTrackerOptions = {
  readonly initialPollIntervalMs?: number;
  readonly maxPollIntervalMs?: number;
  readonly backoffFactor?: number;
};

/**
 * Polls RagGateway.getJob until a terminal status or AbortSignal.
 */
export class JobTracker {
  private readonly initialPollIntervalMs: number;
  private readonly maxPollIntervalMs: number;
  private readonly backoffFactor: number;

  constructor(
    private readonly rag: RagGateway,
    private readonly clock: Clock,
    options: JobTrackerOptions = {},
  ) {
    this.initialPollIntervalMs = options.initialPollIntervalMs ?? 250;
    this.maxPollIntervalMs = options.maxPollIntervalMs ?? 2_000;
    this.backoffFactor = options.backoffFactor ?? 1.5;
  }

  async watch(jobId: string, onUpdate?: JobUpdateCallback, signal?: AbortSignal): Promise<JobInfo> {
    let previous: JobInfo | null = null;
    let intervalMs = this.initialPollIntervalMs;
    for (;;) {
      throwIfAborted(signal);
      const job = await this.rag.getJob(jobId, signal);
      onUpdate?.(job);
      if (TERMINAL.has(job.status)) {
        return job;
      }
      const progressed =
        previous === null || previous.status !== job.status || previous.progress !== job.progress;
      intervalMs = progressed
        ? this.initialPollIntervalMs
        : Math.min(
            this.maxPollIntervalMs,
            Math.max(this.initialPollIntervalMs, Math.round(intervalMs * this.backoffFactor)),
          );
      previous = job;
      await this.clock.sleep(intervalMs, signal);
    }
  }
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}
