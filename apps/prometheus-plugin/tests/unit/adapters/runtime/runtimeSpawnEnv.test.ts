import { mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  buildRuntimeSpawnEnv,
  embeddingCacheNeedsDownload,
  formatOllamaHttpBaseUrl,
} from "../../../../src/adapters/outbound/runtime/runtimeSpawnEnv";

describe("runtimeSpawnEnv", () => {
  it("requests embedding download when cache is empty", async () => {
    const dir = join(tmpdir(), `prom-env-${Date.now()}`);
    await mkdir(dir, { recursive: true });
    await expect(embeddingCacheNeedsDownload(dir)).resolves.toBe(true);
    const env = await buildRuntimeSpawnEnv(dir, { TMPDIR: "/tmp" });
    expect(env.PROMETHEUS_EMBEDDING_ALLOW_DOWNLOAD).toBe("true");
    expect(env.PROMETHEUS_LLM_MODEL).toBe("qwen3:4b");
    expect(env.PROMETHEUS_TOP_K).toBe("6");
    expect(env.PROMETHEUS_EMBEDDING_THREADS).toBe("4");
    expect(env.TMPDIR).toBe(join(dir, "tmp"));
    expect(env.TMP).toBe(join(dir, "tmp"));
    expect(env.TEMP).toBe(join(dir, "tmp"));
    await rm(dir, { recursive: true, force: true });
  });

  it("passes runtime tuning env when provided", async () => {
    const dir = join(tmpdir(), `prom-env-tune-${Date.now()}`);
    await mkdir(dir, { recursive: true });
    const env = await buildRuntimeSpawnEnv(dir, {}, { llmContextSize: 8192 });
    expect(env.PROMETHEUS_LLM_CONTEXT_SIZE).toBe("8192");
    await rm(dir, { recursive: true, force: true });
  });

  it("applies plugin LLM model and Ollama address over process env defaults", async () => {
    const dir = join(tmpdir(), `prom-env-llm-${Date.now()}`);
    await mkdir(dir, { recursive: true });
    const env = await buildRuntimeSpawnEnv(
      dir,
      { PROMETHEUS_LLM_MODEL: "qwen3:4b", PROMETHEUS_LLM_HOST: "http://127.0.0.1:11434" },
      {
        llmModel: "qwen3:4b-instruct-2507-q4_K_M",
        ollamaAddress: "127.0.0.1:11434",
      },
    );
    expect(env.PROMETHEUS_LLM_MODEL).toBe("qwen3:4b-instruct-2507-q4_K_M");
    expect(env.PROMETHEUS_LLM_HOST).toBe("http://127.0.0.1:11434");
    await rm(dir, { recursive: true, force: true });
  });

  it("shrinks the output reserve when context size would not exceed it", async () => {
    const dir = join(tmpdir(), `prom-env-reserve-${Date.now()}`);
    await mkdir(dir, { recursive: true });
    const small = await buildRuntimeSpawnEnv(dir, {}, { llmContextSize: 4096 });
    expect(small.PROMETHEUS_LLM_CONTEXT_SIZE).toBe("4096");
    expect(small.PROMETHEUS_LLM_OUTPUT_RESERVE).toBe("2048");

    const tiny = await buildRuntimeSpawnEnv(dir, {}, { llmContextSize: 1024 });
    expect(tiny.PROMETHEUS_LLM_OUTPUT_RESERVE).toBe("512");

    const roomy = await buildRuntimeSpawnEnv(dir, {}, { llmContextSize: 8192 });
    expect(roomy.PROMETHEUS_LLM_OUTPUT_RESERVE).toBeUndefined();

    const explicit = await buildRuntimeSpawnEnv(
      dir,
      { PROMETHEUS_LLM_OUTPUT_RESERVE: "1000" },
      { llmContextSize: 4096 },
    );
    expect(explicit.PROMETHEUS_LLM_OUTPUT_RESERVE).toBe("1000");
    await rm(dir, { recursive: true, force: true });
  });

  it("formats Ollama host:port as an HTTP base URL", () => {
    expect(formatOllamaHttpBaseUrl("127.0.0.1:11434")).toBe("http://127.0.0.1:11434");
    expect(formatOllamaHttpBaseUrl("http://localhost:11434/")).toBe("http://localhost:11434");
  });

  it("keeps download enabled while incomplete blobs exist", async () => {
    const dir = join(tmpdir(), `prom-env-inc-${Date.now()}`);
    const blobs = join(dir, "models", "embeddings", "models--x", "blobs");
    await mkdir(blobs, { recursive: true });
    await writeFile(join(blobs, "abc.incomplete"), "partial");
    await expect(embeddingCacheNeedsDownload(dir)).resolves.toBe(true);
    await rm(dir, { recursive: true, force: true });
  });
});
