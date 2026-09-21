import { Plugin } from "obsidian";

/**
 * Composition root for the Prometheus Obsidian plugin.
 * Adapters and use cases are wired here in later epics (PLG-E2+).
 */
export default class PrometheusPlugin extends Plugin {
  override async onload(): Promise<void> {
    // Foundation only: registration of views/commands happens in later epics.
  }

  override onunload(): void {
    // Owned runtime stop is implemented in the runtime-manager epic.
  }
}
