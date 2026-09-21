import type { NotePath } from "../../domain/value-objects/NotePath";
import type { SourceReference } from "../../domain/entities/SourceReference";

/** Localhost health probe result (OpenAPI /v1/health). */
export type HealthInfo = {
  readonly status: string;
  readonly version: string;
};

/**
 * Aggregate status from the runtime HTTP API (OpenAPI StatusResponse).
 * Distinct from the plugin's ManagedRuntimeState / RuntimeStatus entities.
 */
export type RuntimeServiceStatus = {
  readonly runtimeVersion: string;
  readonly apiVersion: string;
  readonly indexState: string;
  readonly llmAvailable: boolean;
  readonly llmModel: string;
  readonly documentCount: number;
  readonly chunkCount: number;
  readonly lastIndexedAt: Date | null;
  readonly indexSizeBytes: number;
  readonly reindexRequired: boolean;
  readonly reindexReason: string | null;
};

export type LlmModelInfo = {
  readonly name: string;
  readonly sizeBytes: number;
  readonly quantization: string | null;
};

export type UpsertDocumentInput = {
  readonly path: NotePath;
  readonly content: string;
  readonly revision: number;
  readonly modifiedAt: Date;
};

export type SearchHitDto = {
  readonly path: NotePath;
  readonly heading: string | null;
  readonly text: string;
  readonly score: number;
};

export type ChatAnswerDto = {
  readonly answer: string;
  readonly sources: readonly SourceReference[];
  readonly insufficientContext: boolean;
};

export type JobInfo = {
  readonly jobId: string;
  readonly status: string;
  readonly progress: number;
  readonly error: string | null;
};
