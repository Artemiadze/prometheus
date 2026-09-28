/**
 * Compare installed managed runtime version against the plugin's bundled release.
 * Pure — no network or filesystem access.
 */
export function isUpdateAvailable(
  installed: string | null,
  bundledReleaseVersion: string,
): boolean {
  if (!installed || !bundledReleaseVersion) {
    return false;
  }
  const left = parseLooseSemver(installed);
  const right = parseLooseSemver(bundledReleaseVersion);
  if (!left || !right) {
    return installed !== bundledReleaseVersion;
  }
  for (const key of ["major", "minor", "patch"] as const) {
    if (right[key] > left[key]) {
      return true;
    }
    if (right[key] < left[key]) {
      return false;
    }
  }
  return false;
}

type SemverParts = {
  readonly major: number;
  readonly minor: number;
  readonly patch: number;
};

function parseLooseSemver(value: string): SemverParts | null {
  const match = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)/.exec(value.trim());
  if (!match) {
    return null;
  }
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
  };
}
