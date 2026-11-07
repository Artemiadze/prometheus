import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const packageRoot = join(root, "..");
const repoRoot = join(packageRoot, "..", "..");

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function readTomlVersion(path) {
  const text = readFileSync(path, "utf8");
  const match = text.match(/^version\s*=\s*"([^"]+)"/m);
  if (!match) {
    throw new Error(`version not found in ${path}`);
  }
  return match[1];
}

function readTsExport(path, name) {
  const text = readFileSync(path, "utf8");
  const match = text.match(new RegExp(`export const ${name} = "([^"]+)"`));
  if (!match) {
    throw new Error(`${name} not found in ${path}`);
  }
  return match[1];
}

const expected = "0.1.0";
const packageJson = readJson(join(packageRoot, "package.json"));
const manifest = readJson(join(packageRoot, "manifest.json"));
const rootManifest = readJson(join(repoRoot, "manifest.json"));
const versionsJson = readJson(join(repoRoot, "versions.json"));
const runtimeVersion = readTomlVersion(join(repoRoot, "apps/prometheus-runtime/pyproject.toml"));
const runtimeReleaseVersion = readTsExport(
  join(packageRoot, "src/adapters/outbound/runtime/runtimeRelease.ts"),
  "RUNTIME_RELEASE_VERSION",
);
const requiredRange = readTsExport(
  join(packageRoot, "src/application/services/RuntimeVersion.ts"),
  "REQUIRED_RUNTIME_RANGE",
);

const checks = [
  ["package.json", packageJson.version],
  ["apps/.../manifest.json", manifest.version],
  ["root manifest.json", rootManifest.version],
  ["prometheus-runtime pyproject.toml", runtimeVersion],
  ["RUNTIME_RELEASE_VERSION", runtimeReleaseVersion],
];

const mismatches = checks.filter(([, value]) => value !== expected);
if (mismatches.length > 0) {
  for (const [label, value] of mismatches) {
    console.error(`Version mismatch: ${label}=${value} expected=${expected}`);
  }
  process.exit(1);
}

if (requiredRange !== ">=0.1.0,<0.2.0") {
  console.error(`REQUIRED_RUNTIME_RANGE mismatch: ${requiredRange}`);
  process.exit(1);
}

if (manifest.minAppVersion !== "1.5.0") {
  console.error(`minAppVersion mismatch: ${manifest.minAppVersion} expected=1.5.0`);
  process.exit(1);
}

if (!manifest.author || !manifest.authorUrl) {
  console.error("manifest.json must set author and authorUrl for release");
  process.exit(1);
}

if (manifest.id !== "prometheus") {
  console.error(`manifest id mismatch: ${manifest.id}`);
  process.exit(1);
}

if (JSON.stringify(rootManifest) !== JSON.stringify(manifest)) {
  console.error("root manifest.json must match apps/prometheus-plugin/manifest.json");
  process.exit(1);
}

if (versionsJson[expected] !== manifest.minAppVersion) {
  console.error(
    `versions.json mismatch: versions["${expected}"]=${versionsJson[expected]} expected=${manifest.minAppVersion}`,
  );
  process.exit(1);
}

console.log(
  `release version matrix OK (${expected}); range ${requiredRange}; author=${manifest.author}`,
);
