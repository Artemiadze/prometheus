import { describe, expect, it } from "vitest";

import { SelectLlmModel } from "../../../src/application/use-cases/SelectLlmModel";
import { DEFAULT_PLUGIN_SETTINGS } from "../../../src/application/dto/settings";
import { LlmModelNotFoundError } from "../../../src/domain/errors";
import { FakeRagGateway } from "../../fakes/FakeRagGateway";
import { FakeSettingsRepository } from "../../fakes/FakeSettingsRepository";

describe("SelectLlmModel", () => {
  it("lists local models and marks a removed selection unavailable", async () => {
    const rag = new FakeRagGateway();
    rag.models = [{ name: "qwen3:4b", sizeBytes: 1, quantization: "Q4" }];
    const settings = new FakeSettingsRepository({
      ...DEFAULT_PLUGIN_SETTINGS,
      llmModel: "gone:1b",
    });
    const useCase = new SelectLlmModel(rag, settings);
    const models = await useCase.list();
    expect(models.find((m) => m.name === "gone:1b")?.installed).toBe(false);
    expect(models.find((m) => m.name === "qwen3:4b")?.installed).toBe(true);
  });

  it("persists selection and rejects unknown models", async () => {
    const rag = new FakeRagGateway();
    rag.models = [
      { name: "qwen3:4b", sizeBytes: 1, quantization: "Q4" },
      { name: "gemma3:4b", sizeBytes: 2, quantization: "Q4" },
    ];
    const settings = new FakeSettingsRepository();
    const useCase = new SelectLlmModel(rag, settings);
    const result = await useCase.select("gemma3:4b");
    expect(result.requiresRuntimeRestart).toBe(true);
    expect((await settings.get()).llmModel).toBe("gemma3:4b");
    await expect(useCase.select("cloud-gpt")).rejects.toBeInstanceOf(LlmModelNotFoundError);
  });
});
