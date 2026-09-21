# Prometheus Obsidian plugin

Local-first Obsidian Community Plugin that talks to the Prometheus runtime over
localhost. This package contains only the TypeScript client (`main.js`,
`manifest.json`, `styles.css`).

## Development

```bash
npm ci
npm run typecheck
npm run lint
npm run test
npm run build
```

### Watch mode with a test Vault

Point `TEST_VAULT` at the plugin folder inside an Obsidian Vault:

```bash
export TEST_VAULT="/path/to/Vault/.obsidian/plugins/prometheus"
npm run dev
```

Each rebuild copies `main.js`, `manifest.json`, and `styles.css` into that folder.
If `TEST_VAULT` is unset, watch mode still rebuilds `main.js` and prints a warning.

## Architecture

Layers follow Clean Architecture (`docs/adr/0002-plugin-layer-boundaries.md`):

```text
bootstrap -> adapters -> application -> domain
```

`domain` and `application` must not import `obsidian`, `fetch`, or `child_process`.
