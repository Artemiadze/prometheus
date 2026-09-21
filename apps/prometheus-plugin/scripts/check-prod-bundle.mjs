import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const packageRoot = join(root, "..");
const mainJs = join(packageRoot, "main.js");

if (!existsSync(mainJs)) {
  console.error("main.js is missing; run npm run build first");
  process.exit(1);
}

const contents = readFileSync(mainJs, "utf8");
if (contents.includes("sourceMappingURL")) {
  console.error("production main.js must not contain a source map");
  process.exit(1);
}

for (const required of ["main.js", "manifest.json", "styles.css"]) {
  if (!existsSync(join(packageRoot, required))) {
    console.error(`missing release artifact: ${required}`);
    process.exit(1);
  }
}

const releaseFiles = new Set(["main.js", "manifest.json", "styles.css"]);
const unexpected = readdirSync(packageRoot).filter(
  (name) => name.endsWith(".js.map") || name === "dist",
);
if (unexpected.length > 0) {
  console.error(`unexpected build artifacts: ${unexpected.join(", ")}`);
  process.exit(1);
}

if (!releaseFiles.has("main.js")) {
  console.error("release file set is incomplete");
  process.exit(1);
}

console.log("production bundle check passed (main.js, manifest.json, styles.css; no sourcemap)");
