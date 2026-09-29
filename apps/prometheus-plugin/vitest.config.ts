import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "tests/**/*.test.ts"],
    environment: "node",
    globals: true,
    coverage: {
      provider: "v8",
      include: ["src/domain/**/*.ts"],
      exclude: ["src/domain/**/*.test.ts", "src/domain/**/index.ts"],
      thresholds: {
        lines: 90,
        functions: 90,
        statements: 90,
        branches: 80,
      },
    },
  },
});
