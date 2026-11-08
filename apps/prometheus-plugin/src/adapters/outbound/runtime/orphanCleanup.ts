import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

/**
 * Kill leftover `prometheus-runtime serve` processes for the same data dir.
 * Obsidian reloads can leave orphans that then race on SQLite / ports.
 * Linux/macOS only; no-op on Windows.
 */
export async function killOrphanRuntimeServes(
  binaryPath: string,
  dataDir: string,
  diagnosticsAppend?: (stream: "stdout" | "stderr", chunk: string) => void,
): Promise<number> {
  if (process.platform === "win32") {
    return 0;
  }
  let killed = 0;
  let procEntries: string[] = [];
  try {
    procEntries = await readdir("/proc");
  } catch {
    return 0;
  }

  for (const entry of procEntries) {
    if (!/^\d+$/.test(entry)) {
      continue;
    }
    const pid = Number(entry);
    if (!Number.isFinite(pid) || pid === process.pid) {
      continue;
    }
    let cmdline = "";
    try {
      const raw = await readFile(join("/proc", entry, "cmdline"));
      cmdline = raw.toString("utf8").replace(/\0/g, " ");
    } catch {
      continue;
    }
    if (!cmdline.includes(binaryPath) || !cmdline.includes("serve")) {
      continue;
    }
    if (!cmdline.includes(dataDir)) {
      continue;
    }
    try {
      process.kill(pid, "SIGTERM");
      killed += 1;
      diagnosticsAppend?.("stdout", `[cleanup] sent SIGTERM to orphan pid=${pid}`);
    } catch {
      /* already gone */
    }
  }

  if (killed > 0) {
    await sleep(400);
    // Force-kill survivors.
    for (const entry of procEntries) {
      if (!/^\d+$/.test(entry)) {
        continue;
      }
      const pid = Number(entry);
      let cmdline = "";
      try {
        const raw = await readFile(join("/proc", entry, "cmdline"));
        cmdline = raw.toString("utf8").replace(/\0/g, " ");
      } catch {
        continue;
      }
      if (cmdline.includes(binaryPath) && cmdline.includes("serve") && cmdline.includes(dataDir)) {
        try {
          process.kill(pid, "SIGKILL");
          diagnosticsAppend?.("stdout", `[cleanup] sent SIGKILL to orphan pid=${pid}`);
        } catch {
          /* gone */
        }
      }
    }
  }
  return killed;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
