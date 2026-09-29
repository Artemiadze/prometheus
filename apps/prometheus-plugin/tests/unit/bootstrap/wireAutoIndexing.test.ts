import { describe, expect, it, vi } from "vitest";

import { wireAutoIndexing } from "../../../src/bootstrap/wireAutoIndexing";
import { DocumentSyncState } from "../../../src/application/services/DocumentSyncState";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { FakeClock } from "../../fakes/FakeClock";
import { FakeNotifier } from "../../fakes/FakeNotifier";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";
import { FakeVaultGateway } from "../../fakes/FakeVaultGateway";

describe("wireAutoIndexing", () => {
  it("does not subscribe to vault until applySettingsEnabled", async () => {
    const vault = new FakeVaultGateway();
    const subscribe = vi.spyOn(vault, "subscribe");
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      vaultId: "vault-a1",
      autoIndexing: true,
    });
    const wired = wireAutoIndexing({
      vault,
      rag: new FakeRagGateway(),
      settings,
      syncState: new DocumentSyncState(),
      notifier: new FakeNotifier(),
      clock: new FakeClock(),
    });

    expect(subscribe).not.toHaveBeenCalled();
    expect(wired.isEnabled()).toBe(false);

    wired.setEnabled(true);
    expect(subscribe).not.toHaveBeenCalled();
    expect(wired.isEnabled()).toBe(true);

    await wired.applySettingsEnabled();
    expect(subscribe).toHaveBeenCalledOnce();
    expect(wired.isEnabled()).toBe(true);

    wired.dispose();
  });
});
