$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

if (-not $env:PROMETHEUS_RELEASE_TARGET) {
    $env:PROMETHEUS_RELEASE_TARGET = "win-x64"
}

uv sync --project apps/prometheus-runtime --group packaging --group dev
uv run --project apps/prometheus-runtime --group packaging `
  python packaging/build_frozen.py --target $env:PROMETHEUS_RELEASE_TARGET
