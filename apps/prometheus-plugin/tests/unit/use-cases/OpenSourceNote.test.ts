import { describe, expect, it } from "vitest";

import { OpenSourceNote } from "../../../src/application/use-cases/OpenSourceNote";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { SourceReference } from "../../../src/domain/entities/SourceReference";
import { NoteNotFoundError } from "../../../src/domain/errors";
import { FakeNotifier } from "../../fakes/FakeNotifier";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";
import { FakeVaultGateway } from "../../fakes/FakeVaultGateway";

describe("OpenSourceNote", () => {
  it("opens an existing note with heading and settings mode", async () => {
    const vault = new FakeVaultGateway();
    vault.seed("notes/a.md", "body");
    const notifier = new FakeNotifier();
    const useCase = new OpenSourceNote(
      vault,
      new FakeSettingsRepository({
        ...DEFAULT_PLUGIN_SETTINGS,
        noteOpenMode: "open_new_pane",
      }),
      notifier,
    );
    await useCase.execute(SourceReference.create("notes/a.md", "Intro"));
    expect(vault.openNoteCalls).toHaveLength(1);
    expect(vault.openNoteCalls[0]?.options.heading).toBe("Intro");
    expect(vault.openNoteCalls[0]?.options.mode).toBe("open_new_pane");
  });

  it("notifies when the note is missing", async () => {
    const vault = new FakeVaultGateway();
    const notifier = new FakeNotifier();
    const useCase = new OpenSourceNote(vault, new FakeSettingsRepository(), notifier);
    await expect(useCase.execute(SourceReference.create("missing.md"))).rejects.toBeInstanceOf(
      NoteNotFoundError,
    );
    expect(notifier.records[0]?.level).toBe("warning");
  });
});
