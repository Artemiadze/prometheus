import type { Logger } from "../../../../application/ports/Logger";
import type { Notifier } from "../../../../application/ports/Notifier";
import { presentError, type PresentedError } from "./presentError";

export type ErrorReporterDeps = {
  readonly notifier: Pick<Notifier, "error">;
  readonly logger: Pick<Logger, "error">;
};

/**
 * Central error → user notice + structured log (PLG-74 / PLG-76).
 */
export class ErrorReporter {
  constructor(private readonly deps: ErrorReporterDeps) {}

  report(error: unknown, context?: { readonly notify?: boolean }): PresentedError {
    const presented = presentError(error);
    const notify = context?.notify !== false;
    if (notify) {
      this.deps.notifier.error(presented.message);
    }
    this.deps.logger.error(presented.code, {
      ...(presented.requestId ? { requestId: presented.requestId } : {}),
      action: presented.action,
    });
    return presented;
  }
}
