import { mkdir, readdir } from "node:fs/promises";
import { join } from "node:path";

/**
 * Build env for the sidecar process. Enables first-run embedding download when
 * the local model cache is missing or incomplete.
 *
 * Forces TMPDIR under the managed data root so PyInstaller onefile extraction
 * does not use Obsidian Snap's private /tmp (which can fail mid-extract).
 */
export type RuntimeSpawnTuning = {
  readonly llmContextSize?: number;
  readonly llmModel?: string;
  readonly ollamaAddress?: string;
};

/** Plugin settings store host:port; runtime expects an HTTP base URL. */
export function formatOllamaHttpBaseUrl(address: string): string {
  const trimmed = address.trim();
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed.replace(/\/+$/, "");
  }
  return `http://${trimmed}`;
}

export async function buildRuntimeSpawnEnv(
  dataDir: string,
  baseEnv: NodeJS.ProcessEnv = process.env,
  tuning?: RuntimeSpawnTuning,
): Promise<NodeJS.ProcessEnv> {
  const env: NodeJS.ProcessEnv = { ...baseEnv };
  const needsDownload = await embeddingCacheNeedsDownload(dataDir);
  if (needsDownload) {
    env.PROMETHEUS_EMBEDDING_ALLOW_DOWNLOAD = "true";
  }
  const ollamaAddress = tuning?.ollamaAddress?.trim();
  if (ollamaAddress) {
    env.PROMETHEUS_LLM_HOST = formatOllamaHttpBaseUrl(ollamaAddress);
  } else if (!env.PROMETHEUS_LLM_HOST) {
    env.PROMETHEUS_LLM_HOST = "http://127.0.0.1:11434";
  }
  const llmModel = tuning?.llmModel?.trim();
  if (llmModel) {
    env.PROMETHEUS_LLM_MODEL = llmModel;
  } else if (!env.PROMETHEUS_LLM_MODEL) {
    env.PROMETHEUS_LLM_MODEL = "qwen3:4b";
  }
  if (!env.PROMETHEUS_TOP_K) {
    env.PROMETHEUS_TOP_K = "6";
  }
  if (!env.PROMETHEUS_EMBEDDING_THREADS) {
    env.PROMETHEUS_EMBEDDING_THREADS = "4";
  }
  if (
    tuning?.llmContextSize !== undefined &&
    tuning.llmContextSize > 0 &&
    !env.PROMETHEUS_LLM_CONTEXT_SIZE
  ) {
    env.PROMETHEUS_LLM_CONTEXT_SIZE = String(tuning.llmContextSize);
  }
  ensureOutputReserveFitsContext(env);
  const tmpDir = join(dataDir, "tmp");
  await mkdir(tmpDir, { recursive: true });
  env.TMPDIR = tmpDir;
  env.TMP = tmpDir;
  env.TEMP = tmpDir;
  return env;
}

/** Mirrors prometheus-runtime defaults (bootstrap/config.py). */
const RUNTIME_DEFAULT_CONTEXT_SIZE = 8192;
const RUNTIME_DEFAULT_OUTPUT_RESERVE = 4096;

/**
 * The runtime refuses to start unless `llm_output_reserve < llm_context_size`.
 * A context size chosen in plugin settings (e.g. 4096) can collide with the
 * runtime's default 4096-token reserve, so clamp the reserve to half the context.
 */
function ensureOutputReserveFitsContext(env: NodeJS.ProcessEnv): void {
  const context = parsePositiveInt(env.PROMETHEUS_LLM_CONTEXT_SIZE) ?? RUNTIME_DEFAULT_CONTEXT_SIZE;
  const reserve =
    parsePositiveInt(env.PROMETHEUS_LLM_OUTPUT_RESERVE) ?? RUNTIME_DEFAULT_OUTPUT_RESERVE;
  if (reserve >= context) {
    env.PROMETHEUS_LLM_OUTPUT_RESERVE = String(
      Math.max(1, Math.min(RUNTIME_DEFAULT_OUTPUT_RESERVE, Math.floor(context / 2))),
    );
  }
}

function parsePositiveInt(value: string | undefined): number | null {
  if (value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export async function embeddingCacheNeedsDownload(dataDir: string): Promise<boolean> {
  const embeddingsRoot = join(dataDir, "models", "embeddings");
  let entries: string[] = [];
  try {
    entries = await readdir(embeddingsRoot);
  } catch {
    return true;
  }
  if (entries.length === 0) {
    return true;
  }
  // HuggingFace/fastembed leaves `.incomplete` blobs while downloading.
  return await hasIncompleteBlob(embeddingsRoot, 0);
}

async function hasIncompleteBlob(dir: string, depth: number): Promise<boolean> {
  if (depth > 5) {
    return false;
  }
  let names: string[] = [];
  try {
    names = await readdir(dir);
  } catch {
    return false;
  }
  for (const name of names) {
    if (name.endsWith(".incomplete")) {
      return true;
    }
    if (name === ".locks" || name === "CACHEDIR.TAG") {
      continue;
    }
    if (await hasIncompleteBlob(join(dir, name), depth + 1)) {
      return true;
    }
  }
  return false;
}
