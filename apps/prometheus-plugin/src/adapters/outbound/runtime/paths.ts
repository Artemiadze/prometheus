import { join } from "node:path";

export type PlatformPathsInput = {
  readonly platform: NodeJS.Platform;
  readonly env: NodeJS.ProcessEnv;
  readonly homedir: string;
};

export function resolveDataRoot(input: PlatformPathsInput): string {
  const { platform, env, homedir } = input;
  if (platform === "win32") {
    const localAppData = env.LOCALAPPDATA;
    if (!localAppData) {
      throw new Error("LOCALAPPDATA is required on Windows");
    }
    return join(localAppData, "Prometheus");
  }
  if (platform === "darwin") {
    return join(homedir, "Library", "Application Support", "Prometheus");
  }
  const xdg = env.XDG_DATA_HOME;
  if (xdg) {
    return join(xdg, "prometheus");
  }
  return join(homedir, ".local", "share", "prometheus");
}

export function managedBinaryPath(dataRoot: string, platform: NodeJS.Platform): string {
  const fileName = platform === "win32" ? "prometheus-runtime.exe" : "prometheus-runtime";
  return join(dataRoot, "bin", fileName);
}

export function managedBinDirectory(dataRoot: string): string {
  return join(dataRoot, "bin");
}
