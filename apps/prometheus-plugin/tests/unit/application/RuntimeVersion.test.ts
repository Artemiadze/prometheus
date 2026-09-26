import { describe, expect, it } from "vitest";

import {
  assertRuntimeVersionCompatible,
  isRuntimeVersionCompatible,
  REQUIRED_RUNTIME_RANGE,
} from "../../../src/application/services/RuntimeVersion";
import { RuntimeVersionIncompatibleError } from "../../../src/domain/errors";

describe("RuntimeVersion", () => {
  it.each(["0.1.0", "0.1.1", "0.1.999", "0.1.2+build.4"])(
    "accepts compatible version %s",
    (version) => {
      expect(isRuntimeVersionCompatible(version)).toBe(true);
      expect(() => assertRuntimeVersionCompatible(version)).not.toThrow();
    },
  );

  it.each(["0.0.9", "0.1.0-alpha.1", "0.2.0", "1.0.0", "v0.1.0", "invalid"])(
    "rejects incompatible or malformed version %s",
    (version) => {
      expect(isRuntimeVersionCompatible(version)).toBe(false);
      expect(() => assertRuntimeVersionCompatible(version)).toThrow(
        RuntimeVersionIncompatibleError,
      );
    },
  );

  it("keeps the supported range in one exported policy", () => {
    expect(REQUIRED_RUNTIME_RANGE).toBe(">=0.1.0,<0.2.0");
  });
});
