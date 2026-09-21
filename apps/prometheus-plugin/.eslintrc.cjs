/** @type {import("eslint").Linter.Config} */
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: "module",
    project: "./tsconfig.json",
    tsconfigRootDir: __dirname,
  },
  plugins: ["@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:@typescript-eslint/recommended-requiring-type-checking",
  ],
  env: {
    es2020: true,
    node: true,
  },
  ignorePatterns: ["main.js", "node_modules/", "esbuild.config.mjs", "scripts/", "vitest.config.ts"],
  overrides: [
    {
      files: ["src/domain/**/*.{ts,tsx}", "src/application/**/*.{ts,tsx}"],
      rules: {
        "no-restricted-imports": [
          "error",
          {
            paths: [
              {
                name: "obsidian",
                message:
                  "domain and application must stay free of the Obsidian API; use adapters instead.",
              },
              {
                name: "child_process",
                message:
                  "domain and application must not spawn processes; use RuntimeGateway adapters.",
              },
              {
                name: "node:child_process",
                message:
                  "domain and application must not spawn processes; use RuntimeGateway adapters.",
              },
            ],
            patterns: [
              {
                group: ["**/adapters/**", "*/adapters/*", "adapters/*", "adapters/**"],
                message: "Inner layers must not import adapters.",
              },
            ],
          },
        ],
        "no-restricted-globals": [
          "error",
          {
            name: "fetch",
            message:
              "domain and application must not call fetch; use RagGateway / RuntimeGateway adapters.",
          },
        ],
      },
    },
  ],
  rules: {
    "@typescript-eslint/consistent-type-imports": ["error", { prefer: "type-imports" }],
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
    "@typescript-eslint/require-await": "off",
  },
};
