import { describe, expect, it } from "vitest";

import { CollectDiagnostics } from "../../../src/application/use-cases/CollectDiagnostics";
import { RuntimeSessionRegistry } from "../../../src/application/services/RuntimeSessionRegistry";
import { IndexStatus } from "../../../src/domain/entities/IndexStatus";
import {
  ManagedRuntimeState,
  OllamaState,
  createRuntimeStatus,
} from "../../../src/domain/entities/RuntimeStatus";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { FakeRuntimeGateway } from "../../fakes/FakeRuntimeGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";

describe("CollectDiagnostics", () => {
  it("extracts the runtime port and never includes the session token", async () => {
    const runtimeGateway = new FakeRuntimeGateway();
    runtimeGateway.setProcessState(ManagedRuntimeState.running("1.2.0"));
    runtimeGateway.diagnosticsLines = ["[stdout] Bearer leakedtokenvalue0123456789abcdefzzzz"];

    const sessions = new RuntimeSessionRegistry();
    sessions.set({
      connection: {
        baseUrl: "http://127.0.0.1:8765",
        sessionToken: "must-never-appear-in-snapshot-abcdefgh",
      },
      ownership: "owned",
    });

    const recentEvents = {
      snapshot: () => [
        {
          at: new Date("2026-01-01T00:00:00.000Z"),
          level: "error" as const,
          name: "RUNTIME_UNAVAILABLE",
          fields: {},
        },
      ],
    };

    const collect = new CollectDiagnostics({
      runtimeGateway,
      sessions,
      settings: new FakeSettingsRepository({
        ...DEFAULT_PLUGIN_SETTINGS,
        llmModel: "qwen3:4b",
        ollamaAddress: "127.0.0.1:11434",
      }),
      recentEvents,
      getStatus: () => ({
        runtime: createRuntimeStatus({
          runtime: ManagedRuntimeState.running("1.2.0"),
          ollama: OllamaState.running(),
          selectedModel: { name: "qwen3:4b", installed: true },
        }),
        index: IndexStatus.ready({
          documentCount: 3,
          chunkCount: 30,
          lastIndexedAt: null,
          indexSizeBytes: 100,
        }),
        service: null,
        activeJob: null,
        fetchedAt: new Date(0),
      }),
      environment: {
        pluginVersion: "0.1.0",
        platform: "linux",
        arch: "x64",
        release: "6.8.0",
      },
    });

    const snapshot = await collect.execute();
    expect(snapshot.ports.runtime).toBe(8765);
    expect(snapshot.pluginVersion).toBe("0.1.0");
    expect(snapshot.runtimeVersion).toBe("1.2.0");
    expect(snapshot.components.documentCount).toBe(3);

    const serialized = JSON.stringify(snapshot);
    expect(serialized).not.toContain("must-never-appear");
    expect(serialized).not.toContain("sessionToken");
  });
});
