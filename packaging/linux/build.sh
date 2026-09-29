#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export PROMETHEUS_RELEASE_TARGET="${PROMETHEUS_RELEASE_TARGET:-linux-x64}"

uv sync --project apps/prometheus-runtime --group packaging --group dev
uv run --project apps/prometheus-runtime --group packaging \
  python packaging/build_frozen.py --target "$PROMETHEUS_RELEASE_TARGET"
