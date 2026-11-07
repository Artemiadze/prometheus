#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ARCH="$(uname -m)"
if [[ -z "${PROMETHEUS_RELEASE_TARGET:-}" ]]; then
  if [[ "$ARCH" == "arm64" ]]; then
    export PROMETHEUS_RELEASE_TARGET="macos-arm64"
  else
    echo "Unsupported macOS architecture: ${ARCH}. Apple Silicon (arm64) only." >&2
    echo "onnxruntime no longer publishes Intel macOS wheels." >&2
    exit 1
  fi
fi

uv sync --project apps/prometheus-runtime --group packaging --group dev
uv run --project apps/prometheus-runtime --group packaging \
  python packaging/build_frozen.py --target "$PROMETHEUS_RELEASE_TARGET"
