import { describe, expect, it } from "vitest";

import { NotePath } from "../../src/domain/value-objects/NotePath";
import { SearchScope } from "../../src/domain/value-objects/SearchScope";
import { VaultId } from "../../src/domain/value-objects/VaultId";
import { FakeClock } from "./FakeClock";
import { FakeNotifier } from "./FakeNotifier";
import { FakeRagGateway } from "./FakeRagGateway";
import { FakeRuntimeGateway } from "./FakeRuntimeGateway";
import { FakeSettingsRepository } from "./FakeSettingsRepository";
import { FakeVaultGateway } from "./FakeVaultGateway";

describe("FakeClock", () => {
  it("resolves sleep only after advance covers the delay", async () => {
    const clock = new FakeClock(new Date(1_000));
    let resolved = false;
    const pending = clock.sleep(500).then(() => {
      resolved = true;
    });

    clock.advance(499);
    expect(resolved).toBe(false);
    clock.advance(1);
    await pending;
    expect(resolved).toBe(true);
    expect(clock.now().getTime()).toBe(1_500);
  });
});

describe("FakeRagGateway", () => {
  it("honors AbortSignal", async () => {
    const gateway = new FakeRagGateway();
    const controller = new AbortController();
    controller.abort();
    await expect(gateway.health(controller.signal)).rejects.toMatchObject({
      name: "AbortError",
    });
  });

  it("returns configured search stubs", async () => {
    const gateway = new FakeRagGateway();
    gateway.stubSearchHit("notes/a.md", "hello");
    const hits = await gateway.search(
      VaultId.create("vault-1"),
      "q",
      SearchScope.entireVault(),
      10,
    );
    expect(hits).toHaveLength(1);
    expect(hits[0]?.path.value).toBe("notes/a.md");
  });
});

describe("FakeVaultGateway", () => {
  it("subscribes and unsubscribes from vault events", () => {
    const vault = new FakeVaultGateway();
    const events: string[] = [];
    const unsubscribe = vault.subscribe((event) => {
      events.push(event.type);
    });

    vault.emit({ type: "create", path: NotePath.create("a.md") });
    unsubscribe();
    vault.emit({ type: "modify", path: NotePath.create("a.md") });

    expect(events).toEqual(["create"]);
  });
});

describe("FakeRuntimeGateway", () => {
  it("reports download progress through the callback", async () => {
    const runtime = new FakeRuntimeGateway();
    const seen: number[] = [];
    await runtime.download((progress) => {
      seen.push(progress.percent);
    });
    expect(seen).toEqual([25, 50, 75, 100]);
    expect(runtime.getProcessState().kind).toBe("verifying");
  });
});

describe("FakeSettingsRepository and FakeNotifier", () => {
  it("round-trips settings and records notices", async () => {
    const settings = new FakeSettingsRepository();
    const notifier = new FakeNotifier();
    const current = await settings.get();
    await settings.save({ ...current, llmModel: "gemma3:4b" });
    expect((await settings.get()).llmModel).toBe("gemma3:4b");
    notifier.info("ready");
    expect(notifier.records).toEqual([{ level: "info", message: "ready" }]);
  });
});
