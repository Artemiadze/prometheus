import { RuntimeVersionIncompatibleError } from "../../domain/errors";

export const REQUIRED_RUNTIME_RANGE = ">=0.1.0,<0.2.0";

const MIN_RUNTIME_VERSION = parseSemver("0.1.0");
const MAX_RUNTIME_VERSION = parseSemver("0.2.0");

type Semver = {
  readonly major: number;
  readonly minor: number;
  readonly patch: number;
  readonly prerelease: readonly string[];
};

export function isRuntimeVersionCompatible(version: string): boolean {
  const parsed = tryParseSemver(version);
  if (!parsed) {
    return false;
  }
  return (
    compareSemver(parsed, MIN_RUNTIME_VERSION) >= 0 &&
    compareSemver(parsed, MAX_RUNTIME_VERSION) < 0
  );
}

export function assertRuntimeVersionCompatible(version: string): void {
  if (!isRuntimeVersionCompatible(version)) {
    throw new RuntimeVersionIncompatibleError(version, REQUIRED_RUNTIME_RANGE);
  }
}

function tryParseSemver(value: string): Semver | null {
  try {
    return parseSemver(value);
  } catch {
    return null;
  }
}

function parseSemver(value: string): Semver {
  const match =
    /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/.exec(
      value,
    );
  if (!match) {
    throw new Error("Invalid semantic version");
  }
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    prerelease: match[4]?.split(".") ?? [],
  };
}

function compareSemver(left: Semver, right: Semver): number {
  for (const key of ["major", "minor", "patch"] as const) {
    const delta = left[key] - right[key];
    if (delta !== 0) {
      return delta;
    }
  }
  if (left.prerelease.length === 0 && right.prerelease.length === 0) {
    return 0;
  }
  if (left.prerelease.length === 0) {
    return 1;
  }
  if (right.prerelease.length === 0) {
    return -1;
  }
  const length = Math.max(left.prerelease.length, right.prerelease.length);
  for (let index = 0; index < length; index += 1) {
    const leftPart = left.prerelease[index];
    const rightPart = right.prerelease[index];
    if (leftPart === undefined) {
      return -1;
    }
    if (rightPart === undefined) {
      return 1;
    }
    if (leftPart === rightPart) {
      continue;
    }
    const leftNumber = /^\d+$/.test(leftPart) ? Number(leftPart) : null;
    const rightNumber = /^\d+$/.test(rightPart) ? Number(rightPart) : null;
    if (leftNumber !== null && rightNumber !== null) {
      return leftNumber - rightNumber;
    }
    if (leftNumber !== null) {
      return -1;
    }
    if (rightNumber !== null) {
      return 1;
    }
    return leftPart < rightPart ? -1 : 1;
  }
  return 0;
}
