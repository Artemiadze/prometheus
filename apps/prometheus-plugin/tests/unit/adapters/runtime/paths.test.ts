import { describe, expect, it } from "vitest";

import {
  managedBinaryPath,
  resolveDataRoot,
} from "../../../../src/adapters/outbound/runtime/paths";

describe("runtime paths", () => {
  it("resolves linux data root with XDG_DATA_HOME", () => {
    const root = resolveDataRoot({
      platform: "linux",
      env: { XDG_DATA_HOME: "/xdg/data" },
      homedir: "/home/user",
    });
    expect(root).toBe("/xdg/data/prometheus");
  });

  it("resolves default linux data root", () => {
    const root = resolveDataRoot({
      platform: "linux",
      env: {},
      homedir: "/home/user",
    });
    expect(root).toBe("/home/user/.local/share/prometheus");
  });

  it("prefers SNAP_REAL_HOME over snap-scoped HOME", () => {
    const root = resolveDataRoot({
      platform: "linux",
      env: { SNAP_REAL_HOME: "/home/user" },
      homedir: "/home/user/snap/obsidian/current",
    });
    expect(root).toBe("/home/user/.local/share/prometheus");
  });

  it("strips snap obsidian prefix from homedir when SNAP_REAL_HOME is absent", () => {
    const root = resolveDataRoot({
      platform: "linux",
      env: {},
      homedir: "/home/user/snap/obsidian/68",
    });
    expect(root).toBe("/home/user/.local/share/prometheus");
  });

  it("resolves managed binary path per platform", () => {
    expect(managedBinaryPath("/data", "linux")).toBe("/data/bin/prometheus-runtime");
    expect(managedBinaryPath("/data", "win32")).toBe("/data/bin/prometheus-runtime.exe");
  });
});
