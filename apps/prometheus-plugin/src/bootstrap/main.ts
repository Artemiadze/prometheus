import { Plugin } from "obsidian";

import { ObsidianNotifier } from "../adapters/inbound/notifier/ObsidianNotifier";
import { ObsidianSettingsRepository } from "../adapters/outbound/settings";
import { wireRuntimeLifecycle } from "./wireRuntimeLifecycle";

/**
 * Composition root for the Prometheus Obsidian plugin.
 * Views, commands, and settings tab register in later epics (PLG-E8+).
 */
export default class PrometheusPlugin extends Plugin {
  private disposeRuntimeLifecycle: (() => void) | null = null;

  override async onload(): Promise<void> {
    const settings = new ObsidianSettingsRepository(this);
    const wired = wireRuntimeLifecycle({
      settings,
      notifier: new ObsidianNotifier(),
    });
    this.disposeRuntimeLifecycle = wired.dispose;
  }

  override onunload(): void {
    this.disposeRuntimeLifecycle?.();
    this.disposeRuntimeLifecycle = null;
  }
}
