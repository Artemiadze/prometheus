import type { ChildProcess, spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { describe, expect, it } from "vitest";

import { DEFAULT_PLUGIN_SETTINGS } from "../../../../src/application/dto/settings";
import { RuntimeLocator } from "../../../../src/adapters/outbound/runtime/RuntimeLocator";

describe("RuntimeLocator", () => {
  it("prefers custom binary over managed", async () => {
    const access = async (path: string) => {
      if (path === "/custom/runtime") {
        return;
      }
      throw new Error("missing");
    };
    const locator = new RuntimeLocator({
      getSettings: async () => ({
        ...DEFAULT_PLUGIN_SETTINGS,
        runtimeMode: "managed",
        customBinaryPath: "/custom/runtime",
      }),
      platformPaths: { platform: "linux", env: {}, homedir: "/home/user" },
      access,
      spawnProcess: (() => {
        const stdout = new EventEmitter();
        const child = new EventEmitter() as ChildProcess;
        Object.assign(child, {
          stdout,
          kill: () => undefined,
        });
        queueMicrotask(() => {
          stdout.emit("data", "0.1.0\n");
          child.emit("close", 0);
        });
        return child;
      }) as typeof spawn,
    });
    const result = await locator.locate();
    expect(result.kind).toBe("custom");
    expect(result.version).toBe("0.1.0");
  });

  it("returns missing without throwing", async () => {
    const locator = new RuntimeLocator({
      getSettings: async () => DEFAULT_PLUGIN_SETTINGS,
      platformPaths: { platform: "linux", env: {}, homedir: "/home/user" },
      access: async () => {
        throw new Error("missing");
      },
    });
    await expect(locator.locate()).resolves.toEqual({ kind: "missing", version: null });
  });
});
