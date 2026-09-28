import { describe, expect, it, vi } from "vitest";

import { OnboardingController } from "../../../../../src/adapters/inbound/obsidian/onboarding/OnboardingController";
import { IndexStatus } from "../../../../../src/domain/entities/IndexStatus";
import {
  createRuntimeStatus,
  ManagedRuntimeState,
  OllamaState,
  type OllamaState as OllamaStateType,
} from "../../../../../src/domain/entities/RuntimeStatus";
import type { SystemStatus } from "../../../../../src/application/dto/system";

function statusWithOllama(ollama: OllamaStateType): SystemStatus {
  return {
    runtime: createRuntimeStatus({
      runtime: ManagedRuntimeState.running("0.1.0"),
      ollama,
      selectedModel: null,
    }),
    index: IndexStatus.notIndexed(),
    service: null,
    activeJob: null,
    fetchedAt: new Date(0),
  };
}

describe("OnboardingController", () => {
  it("advances through install and ollama success", async () => {
    const markCompleted = vi.fn(async () => undefined);
    const controller = new OnboardingController({
      installRuntime: async (onState) => {
        onState(ManagedRuntimeState.downloading(100));
      },
      startRuntime: async () => undefined,
      getStatus: async () => statusWithOllama(OllamaState.running()),
      listModels: async () => [
        { name: "qwen3:4b", installed: true, sizeBytes: 1, quantization: "Q4" },
      ],
      selectModel: async () => undefined,
      startInitialSync: async () => undefined,
      cancelActive: async () => null,
      markCompleted,
    });

    await controller.runCurrentStep();
    expect(controller.getState().steps.find((s) => s.id === "install")?.status).toBe("success");
    expect(controller.getState().currentStep).toBe("ollama");

    await controller.runCurrentStep();
    expect(controller.getState().steps.find((s) => s.id === "ollama")?.status).toBe("success");
    expect(controller.getState().currentStep).toBe("model");

    controller.dispose();
  });

  it("keeps ollama step in error until retry succeeds", async () => {
    let ollama: OllamaStateType = OllamaState.stopped();
    const controller = new OnboardingController({
      installRuntime: async () => undefined,
      startRuntime: async () => undefined,
      getStatus: async () => statusWithOllama(ollama),
      listModels: async () => [],
      selectModel: async () => undefined,
      startInitialSync: async () => undefined,
      cancelActive: async () => null,
      markCompleted: async () => undefined,
    });

    await controller.runCurrentStep(); // install -> ollama
    await controller.runCurrentStep(); // ollama error
    expect(controller.getState().steps.find((s) => s.id === "ollama")?.status).toBe("error");

    ollama = OllamaState.running();
    await controller.runCurrentStep(); // retry
    expect(controller.getState().steps.find((s) => s.id === "ollama")?.status).toBe("success");
    controller.dispose();
  });

  it("selectModel advances to index and finish marks completed", async () => {
    const markCompleted = vi.fn(async () => undefined);
    const controller = new OnboardingController({
      installRuntime: async () => undefined,
      startRuntime: async () => undefined,
      getStatus: async () => statusWithOllama(OllamaState.running()),
      listModels: async () => [
        { name: "qwen3:4b", installed: true, sizeBytes: 1, quantization: null },
      ],
      selectModel: async () => undefined,
      startInitialSync: async (_signal, onProgress) => {
        onProgress({ phase: "completed", processed: 1, total: 1 });
      },
      cancelActive: async () => null,
      markCompleted,
    });

    await controller.runCurrentStep(); // install
    await controller.runCurrentStep(); // ollama
    await controller.runCurrentStep(); // load models
    await controller.selectModel("qwen3:4b");
    expect(controller.getState().currentStep).toBe("index");
    await controller.runCurrentStep(); // index
    expect(controller.getState().completed).toBe(true);
    expect(markCompleted).toHaveBeenCalledOnce();
    controller.dispose();
  });
});
