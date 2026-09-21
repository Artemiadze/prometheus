import { LlmModelNotFoundError } from "../../domain/errors";
import type { LlmModelInfo } from "../dto/rag";
import type { RagGateway } from "../ports/RagGateway";
import type { SettingsRepository } from "../ports/SettingsRepository";

export type LlmModelChoice = {
  readonly name: string;
  readonly installed: boolean;
  readonly sizeBytes: number;
  readonly quantization: string | null;
};

export type SelectLlmModelResult = {
  readonly models: readonly LlmModelChoice[];
  readonly selected: string;
  readonly requiresRuntimeRestart: boolean;
};

export class SelectLlmModel {
  constructor(
    private readonly rag: RagGateway,
    private readonly settings: SettingsRepository,
  ) {}

  async list(signal?: AbortSignal): Promise<readonly LlmModelChoice[]> {
    const settings = await this.settings.get();
    const models = await this.rag.listModels(signal);
    return toChoices(models, settings.llmModel);
  }

  async select(modelName: string, signal?: AbortSignal): Promise<SelectLlmModelResult> {
    const settings = await this.settings.get();
    const models = await this.rag.listModels(signal);
    const installed = models.some((model) => model.name === modelName);
    if (!installed) {
      throw new LlmModelNotFoundError(modelName);
    }
    const changed = settings.llmModel !== modelName;
    if (changed) {
      await this.settings.save({ ...settings, llmModel: modelName });
    }
    return {
      models: toChoices(models, modelName),
      selected: modelName,
      requiresRuntimeRestart: changed,
    };
  }
}

function toChoices(models: readonly LlmModelInfo[], selected: string): LlmModelChoice[] {
  const choices = models.map((model) => ({
    name: model.name,
    installed: true,
    sizeBytes: model.sizeBytes,
    quantization: model.quantization,
  }));
  if (selected && !choices.some((choice) => choice.name === selected)) {
    choices.push({
      name: selected,
      installed: false,
      sizeBytes: 0,
      quantization: null,
    });
  }
  return choices;
}
