import type {
  IndexStatus,
  IndexStatus as IndexStatusUnion,
} from "../../domain/entities/IndexStatus";
import type { RuntimeStatus } from "../../domain/entities/RuntimeStatus";
import type { JobInfo, RuntimeServiceStatus } from "./rag";

export type SystemStatus = {
  readonly runtime: RuntimeStatus;
  readonly index: IndexStatusUnion;
  readonly service: RuntimeServiceStatus | null;
  readonly activeJob: JobInfo | null;
  readonly fetchedAt: Date;
};

export type { IndexStatus };
