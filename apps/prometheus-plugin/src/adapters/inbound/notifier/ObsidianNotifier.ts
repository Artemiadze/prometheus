import { Notice } from "obsidian";

import type { Notifier } from "../../../application/ports/Notifier";

export class ObsidianNotifier implements Notifier {
  info(message: string): void {
    new Notice(message, 4_000);
  }

  warning(message: string): void {
    new Notice(message, 6_000);
  }

  error(message: string): void {
    new Notice(message, 8_000);
  }
}
