import { createHash, randomBytes } from "node:crypto";
import { chmod, mkdir, rename, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";

import type { PluginSettings } from "../../../application/dto/settings";
import type { ProgressCallback } from "../../../application/ports/RuntimeGateway";
import {
  RuntimeChecksumMismatchError,
  RuntimeDownloadFailedError,
  isAbortError,
} from "../../../domain/errors";
import { managedBinDirectory } from "./paths";
import type { RuntimeLocator } from "./RuntimeLocator";
import { resolveReleaseDescriptor } from "./runtimeRelease";

export type FetchFn = typeof fetch;

export type RuntimeDownloaderDeps = {
  readonly locator: RuntimeLocator;
  readonly getSettings: () => Promise<PluginSettings>;
  readonly fetchFn: FetchFn;
  readonly platform: NodeJS.Platform;
  readonly arch: string;
};

export class RuntimeDownloader {
  private expectedSha256: string | null = null;

  constructor(private readonly deps: RuntimeDownloaderDeps) {}

  getExpectedSha256(): string | null {
    return this.expectedSha256;
  }

  async download(onProgress: ProgressCallback, signal?: AbortSignal): Promise<void> {
    throwIfAborted(signal);
    const settings = await this.deps.getSettings();
    if (settings.networkAccess === "disabled") {
      throw new RuntimeDownloadFailedError("Runtime download is disabled by privacy settings");
    }

    const descriptor = resolveReleaseDescriptor(this.deps.platform, this.deps.arch);
    const checksumResponse = await this.deps.fetchFn(
      descriptor.checksumUrl,
      withOptionalSignal(signal),
    );
    if (!checksumResponse.ok) {
      throw new RuntimeDownloadFailedError("Failed to fetch runtime checksum");
    }
    const checksumText = await checksumResponse.text();
    this.expectedSha256 = parseChecksumFile(checksumText);

    const binDir = managedBinDirectory(this.deps.locator.dataRootPath());
    await mkdir(binDir, { recursive: true });
    const targetPath = this.deps.locator.managedInstallPath();
    const tempPath = join(binDir, `.download-${randomBytes(8).toString("hex")}`);

    try {
      const binaryResponse = await this.deps.fetchFn(
        descriptor.binaryUrl,
        withOptionalSignal(signal),
      );
      if (!binaryResponse.ok) {
        throw new RuntimeDownloadFailedError("Failed to download runtime binary");
      }
      const contentLengthHeader = binaryResponse.headers.get("content-length");
      const totalBytes =
        contentLengthHeader !== null && contentLengthHeader.length > 0
          ? Number(contentLengthHeader)
          : null;
      const payload = Buffer.from(await binaryResponse.arrayBuffer());
      throwIfAborted(signal);

      const hash = createHash("sha256");
      hash.update(payload);
      if (totalBytes !== null && totalBytes > 0) {
        const percent = Math.min(100, Math.round((payload.length / totalBytes) * 100));
        onProgress({ percent });
      }
      await writeFile(tempPath, payload);

      const digest = hash.digest("hex");
      if (digest !== this.expectedSha256) {
        throw new RuntimeChecksumMismatchError();
      }

      await chmod(tempPath, 0o755);
      await rename(tempPath, targetPath);
      onProgress({ percent: 100 });
    } catch (error) {
      await safeUnlink(tempPath);
      if (isAbortError(error)) {
        throw error;
      }
      if (error instanceof RuntimeChecksumMismatchError) {
        throw error;
      }
      if (error instanceof RuntimeDownloadFailedError) {
        throw error;
      }
      throw new RuntimeDownloadFailedError("Runtime download failed");
    }
  }

  async verifyInstalledBinary(signal?: AbortSignal): Promise<void> {
    throwIfAborted(signal);
    const expected = this.expectedSha256;
    if (!expected) {
      const descriptor = resolveReleaseDescriptor(this.deps.platform, this.deps.arch);
      const checksumResponse = await this.deps.fetchFn(
        descriptor.checksumUrl,
        withOptionalSignal(signal),
      );
      if (!checksumResponse.ok) {
        throw new RuntimeDownloadFailedError("Failed to fetch runtime checksum for verify");
      }
      this.expectedSha256 = parseChecksumFile(await checksumResponse.text());
    }
    await this.verifyFile(this.deps.locator.managedInstallPath(), this.expectedSha256!);
  }

  async verifyFile(path: string, expectedSha256: string): Promise<void> {
    const fileStat = await stat(path).catch(() => null);
    if (!fileStat?.isFile()) {
      throw new RuntimeDownloadFailedError("Runtime binary is not installed");
    }
    const hash = createHash("sha256");
    const { createReadStream } = await import("node:fs");
    await new Promise<void>((resolve, reject) => {
      const read = createReadStream(path);
      read.on("data", (chunk) => {
        hash.update(chunk);
      });
      read.on("error", reject);
      read.on("end", () => {
        resolve();
      });
    });
    if (hash.digest("hex") !== expectedSha256) {
      throw new RuntimeChecksumMismatchError();
    }
  }
}

export function parseChecksumFile(text: string): string {
  const trimmed = text.trim();
  const token = trimmed.split(/\s+/)[0] ?? "";
  if (!/^[a-f0-9]{64}$/i.test(token)) {
    throw new RuntimeDownloadFailedError("Invalid runtime checksum file");
  }
  return token.toLowerCase();
}

async function safeUnlink(path: string): Promise<void> {
  try {
    await rm(path, { force: true });
  } catch {
    /* ignore */
  }
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
}

function withOptionalSignal(signal?: AbortSignal): RequestInit {
  return signal ? { signal } : {};
}
