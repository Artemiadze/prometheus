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

## Local Obsidian testing (manual)

Until Community Plugin / GitHub release hosting is wired (PLG-E16 / PRM-77), install
the frozen runtime yourself and load the plugin from a vault folder.

### 1. Ollama

```bash
ollama pull qwen3:4b
# ensure the daemon answers on loopback
curl -sS http://127.0.0.1:11434/api/tags
```

### 2. Build and install the runtime binary

```bash
cd /path/to/prometheus
make runtime-frozen

mkdir -p "$HOME/.local/share/prometheus/bin"
cp packaging/dist/prometheus-runtime-linux-x64 \
  "$HOME/.local/share/prometheus/bin/prometheus-runtime"
chmod +x "$HOME/.local/share/prometheus/bin/prometheus-runtime"

# local checksum sidecar (verify without a remote release host)
sha256sum "$HOME/.local/share/prometheus/bin/prometheus-runtime" \
  | awk '{print $1 "  prometheus-runtime"}' \
  > "$HOME/.local/share/prometheus/bin/prometheus-runtime.sha256"
```

If Obsidian is installed via Snap, the plugin resolves the real home via
`SNAP_REAL_HOME` so the path above is the correct managed location.

### 3. Build the plugin into a vault

```bash
mkdir -p "$HOME/Documents/MyVault/.obsidian/plugins/prometheus"
export TEST_VAULT="$HOME/Documents/MyVault/.obsidian/plugins/prometheus"
make plugin-build
```

In Obsidian: **Settings → Community plugins → enable Prometheus**
(turn on community plugins if needed). Reload the app after rebuilds
(`Ctrl+P` → “Reload app without saving”).

### 4. Optional env (launch Obsidian from a shell)

```bash
# first-time embedding model download into runtime data dir
export PROMETHEUS_EMBEDDING_ALLOW_DOWNLOAD=true
# default LLM (must match an installed Ollama model)
export PROMETHEUS_LLM_MODEL=qwen3:4b
# only for local debug: skip checksum verify (do not use in release)
# export PROMETHEUS_DEV_SKIP_RUNTIME_VERIFY=true
# optional local/private release mirror base (Node HTTP, not Chromium fetch)
# export PROMETHEUS_RUNTIME_RELEASE_BASE_URL=http://127.0.0.1:8766/runtime

obsidian   # or your desktop launcher; enable Obsidian CLI in Settings if needed
```

### 5. In the Status panel

1. Open **Prometheus Status** (command palette / ribbon).
2. If runtime shows **Stopped** (binary found) → **Restart** / start.
   If **Missing** → **Download** (needs release URL or mirror); with a local
   binary + `.sha256` sidecar, install skips re-download and only verifies.
3. Wait until **Prometheus service** is Running (cold start of the frozen
   binary can take up to ~30s).
4. Confirm **Ollama** is Running and model `qwen3:4b` is available.
5. **Reindex vault**. The **first** reindex downloads the embedding model
   (~500MB–1GB) into `~/.local/share/prometheus/models/embeddings/` and can
   take several minutes — “Failed to index …” during that window usually means
   the download is still running or was blocked. Wait, then reindex again.
6. When Documents/Chunks > 0, use **Chat** / **Search**.

Turn **Automatic indexing** off until the service is Running to avoid sync errors.

If Diagnostics shows `runtime.stopped reason=crashed` or
`Runtime process is already running`, Reload once — Restart now clears orphan
`serve` processes for the same data dir.

### Release note

- Keep Node-based install/verify and real release URLs for production.
- Remove any `127.0.0.1` release base override and do **not** ship with
  `PROMETHEUS_DEV_SKIP_RUNTIME_VERIFY` enabled.

## Architecture

Layers follow Clean Architecture (`docs/adr/0002-plugin-layer-boundaries.md`):

```text
bootstrap -> adapters -> application -> domain
```

`domain` and `application` must not import `obsidian`, `fetch`, or `child_process`.
