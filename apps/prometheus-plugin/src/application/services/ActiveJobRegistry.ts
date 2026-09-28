import type { JobInfo } from "../dto/rag";

/**
 * Shared in-memory handle for the job currently watched by status UI.
 * Updated by indexing use cases; read by GetSystemStatus.getActiveJob.
 */
export class ActiveJobRegistry {
  private job: JobInfo | null = null;

  get(): JobInfo | null {
    return this.job;
  }

  set(job: JobInfo | null): void {
    this.job = job;
  }

  clear(): void {
    this.job = null;
  }
}
