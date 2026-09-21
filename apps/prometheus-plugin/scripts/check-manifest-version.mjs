import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const packageRoot = join(root, "..");

const packageJson = JSON.parse(readFileSync(join(packageRoot, "package.json"), "utf8"));
const manifest = JSON.parse(readFileSync(join(packageRoot, "manifest.json"), "utf8"));

if (packageJson.version !== manifest.version) {
  console.error(
    `Version mismatch: package.json=${packageJson.version} manifest.json=${manifest.version}`,
  );
  process.exit(1);
}

console.log(`manifest version matches package.json (${manifest.version})`);
