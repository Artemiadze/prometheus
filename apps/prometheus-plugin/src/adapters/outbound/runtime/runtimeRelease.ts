import { isRuntimeVersionCompatible } from "../../../application/services/RuntimeVersion";

/**
 * Release artifact policy for the managed runtime downloader.
 *
 * Production assets are published by `.github/workflows/release-runtime.yml` to
 * GitHub Releases. URLs resolve as:
 *   `{BASE}/v{VERSION}/{fileName}`
 *   `{BASE}/v{VERSION}/{fileName}.sha256`
 *
 * Override for local mirrors / private hosts:
 *   PROMETHEUS_RUNTIME_RELEASE_BASE_URL=http://127.0.0.1:8766/runtime
 *
 * Assumption: each platform publishes a single executable file (no archive extraction).
 *
 * Supported targets: linux-x64, win-x64, macos-arm64.
 * macOS Intel (x86_64) is unsupported: onnxruntime dropped those wheels at 1.24+.
 */
export const RUNTIME_RELEASE_BASE_URL =
  "https://github.com/Artemiadze/prometheus/releases/download";

/** Must stay within REQUIRED_RUNTIME_RANGE; validated in unit tests. */
export const RUNTIME_RELEASE_VERSION = "0.1.0";

export type ReleaseTarget = "linux-x64" | "win-x64" | "macos-arm64";

export type RuntimeReleaseDescriptor = {
  readonly binaryUrl: string;
  readonly checksumUrl: string;
  readonly fileName: string;
  readonly version: string;
};

export function resolveReleaseBaseUrl(
  env: NodeJS.ProcessEnv = process.env,
  fallback: string = RUNTIME_RELEASE_BASE_URL,
): string {
  const override = env.PROMETHEUS_RUNTIME_RELEASE_BASE_URL?.trim();
  return override && override.length > 0
    ? override.replace(/\/$/, "")
    : fallback.replace(/\/$/, "");
}

export function detectReleaseTarget(platform: NodeJS.Platform, arch: string): ReleaseTarget {
  if (platform === "win32") {
    return "win-x64";
  }
  if (platform === "darwin") {
    if (arch === "arm64") {
      return "macos-arm64";
    }
    throw new Error(
      `Managed Prometheus Runtime is not available on macOS ${arch}. ` +
        "Apple Silicon (arm64) is required; onnxruntime no longer ships Intel macOS wheels.",
    );
  }
  return "linux-x64";
}

export function releaseFileName(target: ReleaseTarget): string {
  switch (target) {
    case "win-x64":
      return "prometheus-runtime.exe";
    case "linux-x64":
      return "prometheus-runtime-linux-x64";
    case "macos-arm64":
      return "prometheus-runtime-macos-arm64";
    default: {
      const _exhaustive: never = target;
      return _exhaustive;
    }
  }
}

export function resolveReleaseDescriptor(
  platform: NodeJS.Platform,
  arch: string,
  baseUrl: string = resolveReleaseBaseUrl(),
  version: string = RUNTIME_RELEASE_VERSION,
): RuntimeReleaseDescriptor {
  if (!isRuntimeVersionCompatible(version)) {
    throw new Error(`RUNTIME_RELEASE_VERSION ${version} is outside the supported plugin range`);
  }
  const target = detectReleaseTarget(platform, arch);
  const fileName = releaseFileName(target);
  const versionSegment = `v${version}`;
  const prefix = `${baseUrl.replace(/\/$/, "")}/${versionSegment}`;
  return {
    binaryUrl: `${prefix}/${fileName}`,
    checksumUrl: `${prefix}/${fileName}.sha256`,
    fileName,
    version,
  };
}
