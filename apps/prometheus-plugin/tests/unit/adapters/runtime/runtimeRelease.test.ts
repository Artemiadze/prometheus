import { describe, expect, it } from "vitest";

import { isRuntimeVersionCompatible } from "../../../../src/application/services/RuntimeVersion";
import {
  RUNTIME_RELEASE_BASE_URL,
  RUNTIME_RELEASE_VERSION,
  detectReleaseTarget,
  resolveReleaseBaseUrl,
  resolveReleaseDescriptor,
} from "../../../../src/adapters/outbound/runtime/runtimeRelease";

describe("runtimeRelease", () => {
  it("keeps RUNTIME_RELEASE_VERSION inside the plugin compatibility range", () => {
    expect(isRuntimeVersionCompatible(RUNTIME_RELEASE_VERSION)).toBe(true);
  });

  it("detects platform targets", () => {
    expect(detectReleaseTarget("linux", "x64")).toBe("linux-x64");
    expect(detectReleaseTarget("win32", "x64")).toBe("win-x64");
    expect(detectReleaseTarget("darwin", "arm64")).toBe("macos-arm64");
  });

  it("builds release URLs", () => {
    const descriptor = resolveReleaseDescriptor("linux", "x64", "https://example.test/runtime");
    expect(descriptor.binaryUrl).toContain("prometheus-runtime-linux-x64");
    expect(descriptor.checksumUrl).toContain(".sha256");
  });

  it("uses GitHub Releases download base by default", () => {
    const descriptor = resolveReleaseDescriptor("linux", "x64");
    expect(descriptor.binaryUrl).toBe(
      "https://github.com/Artemiadze/prometheus/releases/download/v0.1.0/prometheus-runtime-linux-x64",
    );
    expect(descriptor.checksumUrl).toBe(
      "https://github.com/Artemiadze/prometheus/releases/download/v0.1.0/prometheus-runtime-linux-x64.sha256",
    );
    expect(RUNTIME_RELEASE_BASE_URL).toBe(
      "https://github.com/Artemiadze/prometheus/releases/download",
    );
  });

  it("allows PROMETHEUS_RUNTIME_RELEASE_BASE_URL override", () => {
    expect(resolveReleaseBaseUrl({})).toBe(RUNTIME_RELEASE_BASE_URL.replace(/\/$/, ""));
    expect(
      resolveReleaseBaseUrl({
        PROMETHEUS_RUNTIME_RELEASE_BASE_URL: "http://127.0.0.1:8766/runtime/",
      }),
    ).toBe("http://127.0.0.1:8766/runtime");
  });
});
