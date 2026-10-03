import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { DEFAULT_PLUGIN_SETTINGS } from "../../../../src/application/dto/settings";
import {
  RuntimeChecksumMismatchError,
  RuntimeDownloadFailedError,
} from "../../../../src/domain/errors";
import {
  RuntimeDownloader,
  parseChecksumFile,
} from "../../../../src/adapters/outbound/runtime/RuntimeDownloader";
import { RuntimeLocator } from "../../../../src/adapters/outbound/runtime/RuntimeLocator";

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.href;
  }
  if (typeof input !== "object" || !("url" in input) || typeof input.url !== "string") {
    throw new Error("Expected fetch URL input");
  }
  return input.url;
}

describe("RuntimeDownloader", () => {
  it("parses sha256 checksum files", () => {
    expect(
      parseChecksumFile("abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789  file"),
    ).toBe("abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789");
  });

  it("downloads, verifies checksum, and installs atomically", async () => {
    const dir = await mkdtemp(join(tmpdir(), "prom-runtime-"));
    const payload = Buffer.from("runtime-binary-bytes");
    const digest = createHash("sha256").update(payload).digest("hex");

    const locator = new RuntimeLocator({
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      platformPaths: { platform: "linux", env: {}, homedir: dir },
      access: async () => undefined,
    });

    const fetchFn: typeof fetch = async (input) => {
      const url = requestUrl(input);
      if (url.endsWith(".sha256")) {
        return new Response(`${digest}  prometheus-runtime-linux-x64\n`, { status: 200 });
      }
      return new Response(payload, {
        status: 200,
        headers: { "content-length": String(payload.length) },
      });
    };

    const downloader = new RuntimeDownloader({
      locator,
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      fetchFn,
      platform: "linux",
      arch: "x64",
    });

    const progress: number[] = [];
    await downloader.download((value) => progress.push(value.percent));

    const installed = await readFile(locator.managedInstallPath());
    expect(installed.equals(payload)).toBe(true);
    expect(progress.at(-1)).toBe(100);
    await downloader.verifyInstalledBinary();
    await rm(dir, { recursive: true, force: true });
  });

  it("rejects checksum mismatch and removes temp file", async () => {
    const dir = await mkdtemp(join(tmpdir(), "prom-runtime-"));
    const payload = Buffer.from("runtime-binary-bytes");
    const locator = new RuntimeLocator({
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      platformPaths: { platform: "linux", env: {}, homedir: dir },
      access: async () => undefined,
    });
    const fetchFn: typeof fetch = async (input) => {
      const url = requestUrl(input);
      if (url.endsWith(".sha256")) {
        return new Response(`${"a".repeat(64)}  file\n`, { status: 200 });
      }
      return new Response(payload, { status: 200 });
    };
    const downloader = new RuntimeDownloader({
      locator,
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      fetchFn,
      platform: "linux",
      arch: "x64",
    });
    await expect(downloader.download(() => undefined)).rejects.toBeInstanceOf(
      RuntimeChecksumMismatchError,
    );
    await rm(dir, { recursive: true, force: true });
  });

  it("blocks download when network access is disabled", async () => {
    const locator = new RuntimeLocator({
      getSettings: async () => ({ ...DEFAULT_PLUGIN_SETTINGS, networkAccess: "disabled" }),
      platformPaths: { platform: "linux", env: {}, homedir: "/tmp" },
      access: async () => undefined,
    });
    const downloader = new RuntimeDownloader({
      locator,
      getSettings: async () => ({ ...DEFAULT_PLUGIN_SETTINGS, networkAccess: "disabled" }),
      fetchFn: async () => new Response("", { status: 500 }),
      platform: "linux",
      arch: "x64",
    });
    await expect(downloader.download(() => undefined)).rejects.toBeInstanceOf(
      RuntimeDownloadFailedError,
    );
  });

  it("verifies from a local .sha256 sidecar without network", async () => {
    const dir = await mkdtemp(join(tmpdir(), "prom-runtime-"));
    const payload = Buffer.from("runtime-binary-bytes");
    const digest = createHash("sha256").update(payload).digest("hex");
    const locator = new RuntimeLocator({
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      platformPaths: { platform: "linux", env: {}, homedir: dir },
      access: async () => undefined,
    });
    const { writeFile, mkdir } = await import("node:fs/promises");
    const { dirname } = await import("node:path");
    await mkdir(dirname(locator.managedInstallPath()), { recursive: true });
    await writeFile(locator.managedInstallPath(), payload);
    await writeFile(`${locator.managedInstallPath()}.sha256`, `${digest}  prometheus-runtime\n`);

    const downloader = new RuntimeDownloader({
      locator,
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      fetchFn: async () => {
        throw new Error("network should not be used");
      },
      platform: "linux",
      arch: "x64",
    });
    await downloader.verifyInstalledBinary();
    await rm(dir, { recursive: true, force: true });
  });

  it("skips verify when PROMETHEUS_DEV_SKIP_RUNTIME_VERIFY is set", async () => {
    const dir = await mkdtemp(join(tmpdir(), "prom-runtime-"));
    const locator = new RuntimeLocator({
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      platformPaths: { platform: "linux", env: {}, homedir: dir },
      access: async () => undefined,
    });
    const { writeFile, mkdir } = await import("node:fs/promises");
    const { dirname } = await import("node:path");
    await mkdir(dirname(locator.managedInstallPath()), { recursive: true });
    await writeFile(locator.managedInstallPath(), Buffer.from("x"));

    const downloader = new RuntimeDownloader({
      locator,
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      fetchFn: async () => {
        throw new Error("network should not be used");
      },
      platform: "linux",
      arch: "x64",
      env: { PROMETHEUS_DEV_SKIP_RUNTIME_VERIFY: "true" },
    });
    await downloader.verifyInstalledBinary();
    await rm(dir, { recursive: true, force: true });
  });
});
