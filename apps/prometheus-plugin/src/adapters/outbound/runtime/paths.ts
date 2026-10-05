import { join } from "node:path";

export type PlatformPathsInput = {
  readonly platform: NodeJS.Platform;
  readonly env: NodeJS.ProcessEnv;
  readonly homedir: string;
};

/**
 * Prefer the real user home when Obsidian runs as a Snap.
 * Snap often sets HOME to ~/snap/obsidian/current while binaries are installed
 * under the real ~/.local/share/prometheus.
 */
export function resolveEffectiveHomedir(input: PlatformPathsInput): string {
  const { env, homedir } = input;
  const snapRealHome = env.SNAP_REAL_HOME?.trim();
  if (snapRealHome && snapRealHome.length > 0) {
    return snapRealHome;
  }
  // Fallback: if HOME looks like a snap user data dir, strip to the real home.
  const snapMarker = "/snap/obsidian/";
  const idx = homedir.indexOf(snapMarker);
  if (idx > 0) {
    return homedir.slice(0, idx);
  }
  return homedir;
}

export function resolveDataRoot(input: PlatformPathsInput): string {
  const { platform, env } = input;
  const homedir = resolveEffectiveHomedir(input);
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
  // Prefer real-home XDG over snap-scoped XDG_DATA_HOME when Snap remaps HOME.
  const xdg = env.XDG_DATA_HOME;
  const snapRealHome = env.SNAP_REAL_HOME?.trim();
  if (xdg && !(snapRealHome && xdg.includes("/snap/obsidian/"))) {
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
