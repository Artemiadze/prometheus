import { describe, expect, it } from "vitest";

import {
  isPrometheusPluginError,
  LlmModelNotFoundError,
  RuntimeChecksumMismatchError,
  RuntimeNotInstalledError,
  RuntimeUnavailableError,
  RuntimeVersionIncompatibleError,
  VaultNotIndexedError,
} from "./errors";

describe("PrometheusPluginError hierarchy", () => {
  it("exposes stable codes aligned with the runtime envelope where applicable", () => {
    expect(new RuntimeNotInstalledError().code).toBe("RUNTIME_NOT_INSTALLED");
    expect(new RuntimeChecksumMismatchError().code).toBe("RUNTIME_CHECKSUM_MISMATCH");
    expect(new RuntimeUnavailableError().code).toBe("RUNTIME_UNAVAILABLE");
    expect(new VaultNotIndexedError().code).toBe("VAULT_NOT_INDEXED");
    expect(new LlmModelNotFoundError("qwen3:4b").code).toBe("LLM_MODEL_NOT_FOUND");
    expect(new RuntimeVersionIncompatibleError("0.0.1", ">=0.1.0,<0.2.0").code).toBe(
      "RUNTIME_VERSION_INCOMPATIBLE",
    );
  });

  it("keeps messages free of note text and session tokens", () => {
    const versionError = new RuntimeVersionIncompatibleError("0.0.1", ">=0.1.0,<0.2.0");
    expect(versionError.message).toContain("0.0.1");
    expect(versionError.message).toContain(">=0.1.0,<0.2.0");
    expect(versionError.message.toLowerCase()).not.toContain("token");
    expect(versionError.message).not.toContain("session");

    const modelError = new LlmModelNotFoundError("qwen3:4b");
    expect(modelError.message).toContain("qwen3:4b");
    expect(modelError.message).not.toMatch(/#\s|```/);
  });

  it("identifies plugin errors via type guard", () => {
    expect(isPrometheusPluginError(new RuntimeNotInstalledError())).toBe(true);
    expect(isPrometheusPluginError(new Error("other"))).toBe(false);
  });
});
