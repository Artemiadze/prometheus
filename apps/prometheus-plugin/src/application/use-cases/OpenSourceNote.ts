import type { SourceReference } from "../../domain/entities/SourceReference";
import { NoteNotFoundError } from "../../domain/errors";
import type { Notifier } from "../ports/Notifier";
import type { SettingsRepository } from "../ports/SettingsRepository";
import type { VaultGateway } from "../ports/VaultGateway";

export class OpenSourceNote {
  constructor(
    private readonly vault: VaultGateway,
    private readonly settings: SettingsRepository,
    private readonly notifier: Notifier,
  ) {}

  async execute(source: SourceReference, signal?: AbortSignal): Promise<void> {
    const settings = await this.settings.get();
    try {
      await this.vault.readFile(source.notePath, signal);
    } catch {
      this.notifier.warning(
        `Note not found: ${source.notePath.value}. It may have been moved or deleted.`,
      );
      throw new NoteNotFoundError(source.notePath.value);
    }

    await this.vault.openNote(
      source.notePath,
      {
        heading: source.heading,
        mode: settings.noteOpenMode,
      },
      signal,
    );
  }
}
