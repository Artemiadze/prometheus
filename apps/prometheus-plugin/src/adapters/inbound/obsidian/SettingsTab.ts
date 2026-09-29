import { PluginSettingTab, Setting, type App, type Plugin } from "obsidian";

import type { SettingsController, SettingsViewState } from "./settings/SettingsController";
import { formatBytes } from "./settings/formatBytes";

/**
 * Obsidian settings tab for Prometheus (PLG-E11).
 */
export class SettingsTab extends PluginSettingTab {
  private readonly controller: SettingsController;
  private unsubscribe: (() => void) | null = null;

  constructor(app: App, plugin: Plugin, controller: SettingsController) {
    super(app, plugin);
    this.controller = controller;
  }

  override display(): void {
    this.unsubscribe?.();
    this.unsubscribe = this.controller.subscribe((state) => {
      this.render(state);
    });
  }

  override hide(): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
  }

  private render(state: SettingsViewState): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.addClass("prometheus-settings");

    containerEl.createEl("h2", { text: "Prometheus Settings" });

    if (state.actionError) {
      containerEl.createDiv({
        cls: "prometheus-settings__error",
        text: state.actionError,
      });
    }

    this.renderRuntime(containerEl, state);
    this.renderIndexing(containerEl, state);
    this.renderEmbeddings(containerEl, state);
    this.renderLlm(containerEl, state);
    this.renderPrivacy(containerEl, state);
    this.renderDiagnostics(containerEl, state);
  }

  private renderRuntime(containerEl: HTMLElement, state: SettingsViewState): void {
    containerEl.createEl("h3", {
      text: "Runtime",
      cls: "prometheus-settings__section-title",
    });
    const section = containerEl.createDiv({ cls: "prometheus-settings__section" });

    new Setting(section)
      .setName("Prometheus Runtime")
      .setDesc("Managed (downloaded) or a custom binary path.")
      .addDropdown((dropdown) => {
        dropdown
          .addOption("managed", "Managed (downloaded)")
          .addOption("custom", "Custom binary")
          .setValue(state.settings.runtimeMode)
          .onChange((value) => {
            void this.controller.updateRuntimeMode(value === "custom" ? "custom" : "managed");
          });
        dropdown.setDisabled(state.actionBusy);
      });

    new Setting(section)
      .setName("Custom binary path")
      .setDesc("Optional absolute path to prometheus-runtime.")
      .addText((text) => {
        text
          .setPlaceholder("/path/to/prometheus-runtime")
          .setValue(state.settings.customBinaryPath ?? "")
          .onChange((value) => {
            // Debounce via blur-style commit on setting change end — Setting fires per keystroke.
            text.inputEl.dataset["pending"] = value;
          });
        text.inputEl.addEventListener("blur", () => {
          const pending = text.inputEl.dataset["pending"];
          if (pending !== undefined) {
            void this.controller.updateCustomBinaryPath(pending);
          }
        });
        text.setDisabled(state.actionBusy || state.settings.runtimeMode !== "custom");
      });

    const versionLabel = formatRuntimeVersion(state);
    new Setting(section).setName("Runtime version").setDesc(versionLabel);

    new Setting(section)
      .setName("Install / update")
      .setDesc(
        state.updateAvailable
          ? "A newer or incompatible runtime is available."
          : "Download or reinstall the managed runtime.",
      )
      .addButton((button) => {
        const showUpdate = state.updateAvailable || state.runtimeState?.kind === "missing";
        button
          .setButtonText(state.updateAvailable ? "Update runtime" : "Install runtime")
          .setDisabled(state.actionBusy || (!showUpdate && state.runtimeState?.kind === "running"))
          .onClick(() => {
            void this.controller.installOrUpdateRuntime();
          });
        if (state.updateAvailable) {
          button.setCta();
        }
      });

    new Setting(section).setName("Restart runtime").addButton((button) => {
      button
        .setButtonText("Restart")
        .setDisabled(state.actionBusy)
        .onClick(() => {
          void this.controller.restartRuntime();
        });
    });

    new Setting(section)
      .setName("Start runtime when Obsidian opens")
      .setDesc(
        "Off by default. When enabled, Prometheus starts the local runtime after the vault loads.",
      )
      .addToggle((toggle) => {
        toggle
          .setValue(state.settings.runtimeAutostart)
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            void this.controller.setRuntimeAutostart(value);
          });
      });
  }

  private renderIndexing(containerEl: HTMLElement, state: SettingsViewState): void {
    containerEl.createEl("h3", {
      text: "Indexing",
      cls: "prometheus-settings__section-title",
    });
    const section = containerEl.createDiv({ cls: "prometheus-settings__section" });

    new Setting(section)
      .setName("Automatic indexing")
      .setDesc("Index vault changes as they happen.")
      .addToggle((toggle) => {
        toggle
          .setValue(state.settings.autoIndexing)
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            void this.controller.setAutoIndexing(value);
          });
      });

    new Setting(section)
      .setName("Ignored folders")
      .setDesc("Relative vault paths, one per line (must exist).")
      .addTextArea((area) => {
        area.setValue(state.settings.ignoredFolders.join("\n")).setDisabled(state.actionBusy);
        area.inputEl.rows = 4;
        area.inputEl.addEventListener("blur", () => {
          void this.syncIgnoredFolders(area.getValue(), state.settings.ignoredFolders);
        });
      });

    new Setting(section)
      .setName("Chunk size")
      .setDesc("Tokens per chunk (local preference; changing requires reindex).")
      .addText((text) => {
        text
          .setValue(String(state.settings.chunkSizeTokens))
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            text.inputEl.dataset["pending"] = value;
          });
        text.inputEl.addEventListener("blur", () => {
          const pending = text.inputEl.dataset["pending"];
          if (pending !== undefined) {
            const parsed = Number(pending);
            void this.controller.setChunkSize(parsed);
          }
        });
      });

    new Setting(section)
      .setName("Overlap")
      .setDesc("Token overlap between chunks (local preference).")
      .addText((text) => {
        text
          .setValue(String(state.settings.chunkOverlapTokens))
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            text.inputEl.dataset["pending"] = value;
          });
        text.inputEl.addEventListener("blur", () => {
          const pending = text.inputEl.dataset["pending"];
          if (pending !== undefined) {
            void this.controller.setChunkOverlap(Number(pending));
          }
        });
      });

    if (state.chunkReindexWarning) {
      section.createDiv({
        cls: "prometheus-settings__warning",
        text: "Changing chunk size or overlap requires a full reindex to take effect.",
      });
    }

    new Setting(section).setName("Reindex vault").addButton((button) => {
      button
        .setButtonText("Reindex")
        .setDisabled(state.actionBusy)
        .setCta()
        .onClick(() => {
          void this.controller.triggerReindex();
        });
    });
  }

  private renderEmbeddings(containerEl: HTMLElement, state: SettingsViewState): void {
    containerEl.createEl("h3", {
      text: "Embeddings",
      cls: "prometheus-settings__section-title",
    });
    const section = containerEl.createDiv({ cls: "prometheus-settings__section" });

    new Setting(section).setName("Provider").setDesc("FastEmbed");
    new Setting(section).setName("Model").setDesc("multilingual model");
    section.createDiv({
      cls: "prometheus-settings__note",
      text: "Changing the embedding model requires a full reindex.",
    });

    containerEl.createEl("h3", {
      text: "Vector storage",
      cls: "prometheus-settings__section-title",
    });
    const storage = containerEl.createDiv({ cls: "prometheus-settings__section" });
    new Setting(storage).setName("Store").setDesc("Qdrant Local");
    new Setting(storage).setName("Path").setDesc(state.dataRootPath);
    const indexSize = state.service?.indexSizeBytes;
    new Setting(storage)
      .setName("Index size")
      .setDesc(indexSize === undefined ? "—" : formatBytes(indexSize));
    new Setting(storage)
      .setName("Documents / chunks")
      .setDesc(
        state.service
          ? `${state.service.documentCount.toLocaleString()} / ${state.service.chunkCount.toLocaleString()}`
          : "—",
      );
  }

  private renderLlm(containerEl: HTMLElement, state: SettingsViewState): void {
    containerEl.createEl("h3", {
      text: "LLM",
      cls: "prometheus-settings__section-title",
    });
    const section = containerEl.createDiv({ cls: "prometheus-settings__section" });

    new Setting(section).setName("Runtime").setDesc("Ollama (local)");

    new Setting(section)
      .setName("Model")
      .setDesc("Only locally installed Ollama models are listed.")
      .addDropdown((dropdown) => {
        if (state.models.length === 0) {
          dropdown.addOption(state.settings.llmModel || "none", state.settings.llmModel || "—");
        } else {
          for (const model of state.models) {
            const label = model.installed ? model.name : `${model.name} (not installed)`;
            dropdown.addOption(model.name, label);
          }
        }
        dropdown.setValue(state.settings.llmModel);
        dropdown.setDisabled(state.actionBusy || state.models.length === 0);
        dropdown.onChange((value) => {
          void this.controller.selectModel(value);
        });
      })
      .addButton((button) => {
        button
          .setButtonText("Refresh")
          .setDisabled(state.actionBusy)
          .onClick(() => {
            void this.controller.refreshModels();
          });
      });

    const selected = state.models.find((model) => model.name === state.settings.llmModel);
    if (selected && !selected.installed) {
      section.createDiv({
        cls: "prometheus-settings__warning",
        text: `Selected model ${selected.name} is not installed locally.`,
      });
    }

    new Setting(section)
      .setName("Address")
      .setDesc("Ollama host:port")
      .addText((text) => {
        text
          .setValue(state.settings.ollamaAddress)
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            text.inputEl.dataset["pending"] = value;
          });
        text.inputEl.addEventListener("blur", () => {
          const pending = text.inputEl.dataset["pending"];
          if (pending !== undefined) {
            void this.controller.updateOllamaAddress(pending);
          }
        });
      });

    new Setting(section)
      .setName("Temperature")
      .setDesc("Local preference (0–2). Not yet sent to the runtime.")
      .addText((text) => {
        text
          .setValue(String(state.settings.llmTemperature))
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            text.inputEl.dataset["pending"] = value;
          });
        text.inputEl.addEventListener("blur", () => {
          const pending = text.inputEl.dataset["pending"];
          if (pending !== undefined) {
            void this.controller.setTemperature(Number(pending));
          }
        });
      });

    new Setting(section)
      .setName("Context size")
      .setDesc("Local preference. Not yet sent to the runtime.")
      .addText((text) => {
        text
          .setValue(String(state.settings.llmContextSize))
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            text.inputEl.dataset["pending"] = value;
          });
        text.inputEl.addEventListener("blur", () => {
          const pending = text.inputEl.dataset["pending"];
          if (pending !== undefined) {
            void this.controller.setContextSize(Number(pending));
          }
        });
      });
  }

  private renderPrivacy(containerEl: HTMLElement, state: SettingsViewState): void {
    containerEl.createEl("h3", {
      text: "Privacy",
      cls: "prometheus-settings__section-title",
    });
    const section = containerEl.createDiv({ cls: "prometheus-settings__section" });

    new Setting(section)
      .setName("Network access")
      .setDesc("Updates only allows runtime downloads. Disabled blocks all network installs.")
      .addDropdown((dropdown) => {
        dropdown
          .addOption("updates_only", "Updates only")
          .addOption("disabled", "Disabled")
          .setValue(state.settings.networkAccess)
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            void this.controller.setNetworkAccess(
              value === "disabled" ? "disabled" : "updates_only",
            );
          });
      });

    section.createDiv({
      cls: "prometheus-settings__note",
      text: "No cloud LLM or embedding API is used in the base mode. Local requests to the Prometheus runtime and Ollama are unaffected by this setting.",
    });
  }

  private renderDiagnostics(containerEl: HTMLElement, state: SettingsViewState): void {
    containerEl.createEl("h3", {
      text: "Diagnostics",
      cls: "prometheus-settings__section-title",
    });
    const section = containerEl.createDiv({ cls: "prometheus-settings__section" });

    new Setting(section)
      .setName("Verbose logging")
      .setDesc(
        "Off by default. When enabled, structured debug events go to the developer console. Note text is never logged.",
      )
      .addToggle((toggle) => {
        toggle
          .setValue(state.settings.verboseLogging)
          .setDisabled(state.actionBusy)
          .onChange((value) => {
            void this.controller.setVerboseLogging(value);
          });
      });

    new Setting(section)
      .setName("Diagnostics report")
      .setDesc(
        "Versions, ports, recent errors, and runtime process output. Safe to share in an issue.",
      )
      .addButton((button) => {
        button.setButtonText("Open diagnostics").onClick(() => {
          this.controller.openDiagnostics();
        });
      });
  }

  private async syncIgnoredFolders(
    textareaValue: string,
    current: readonly string[],
  ): Promise<void> {
    const desired = textareaValue
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
    for (const path of current) {
      if (!desired.includes(path)) {
        await this.controller.removeIgnoredFolder(path);
      }
    }
    const afterRemove = new Set(desired.filter((path) => current.includes(path)));
    // Re-read desired that are new
    for (const path of desired) {
      if (!current.includes(path) && !afterRemove.has(path)) {
        await this.controller.addIgnoredFolder(path);
      }
    }
  }
}

function formatRuntimeVersion(state: SettingsViewState): string {
  const runtime = state.runtimeState;
  if (!runtime) {
    return "Unknown";
  }
  switch (runtime.kind) {
    case "running":
      return runtime.version;
    case "incompatible":
      return `${runtime.installedVersion} (incompatible; required ${runtime.requiredRange})`;
    case "missing":
      return "Not installed";
    case "downloading":
      return `Downloading… ${runtime.progressPercent}%`;
    case "verifying":
      return "Verifying…";
    case "starting":
      return "Starting…";
    case "stopped":
      return "Stopped";
    default: {
      const _exhaustive: never = runtime;
      return _exhaustive;
    }
  }
}
