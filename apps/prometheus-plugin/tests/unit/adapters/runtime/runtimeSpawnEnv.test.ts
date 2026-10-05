import { mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  buildRuntimeSpawnEnv,
  embeddingCacheNeedsDownload,
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

  it("keeps download enabled while incomplete blobs exist", async () => {
    const dir = join(tmpdir(), `prom-env-inc-${Date.now()}`);
    const blobs = join(dir, "models", "embeddings", "models--x", "blobs");
    await mkdir(blobs, { recursive: true });
    await writeFile(join(blobs, "abc.incomplete"), "partial");
    await expect(embeddingCacheNeedsDownload(dir)).resolves.toBe(true);
    await rm(dir, { recursive: true, force: true });
  });
});
