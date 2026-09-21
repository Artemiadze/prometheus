import type { JobInfo, JobStatus } from "../dto/rag";
import type { Clock } from "../ports/Clock";
import type { RagGateway } from "../ports/RagGateway";

const TERMINAL: ReadonlySet<JobStatus> = new Set(["completed", "failed", "cancelled"]);

export type JobUpdateCallback = (job: JobInfo) => void;

/**
 * Polls RagGateway.getJob until a terminal status or AbortSignal.
 */
export class JobTracker {
  constructor(
    private readonly rag: RagGateway,
    private readonly clock: Clock,
    private readonly pollIntervalMs = 50,
  ) {}

  async watch(jobId: string, onUpdate?: JobUpdateCallback, signal?: AbortSignal): Promise<JobInfo> {
    for (;;) {
      throwIfAborted(signal);
      const job = await this.rag.getJob(jobId, signal);
      onUpdate?.(job);
      if (TERMINAL.has(job.status)) {
        return job;
      }
      await this.clock.sleep(this.pollIntervalMs, signal);
    }
  }
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}
