"""Command-line entry point for the Prometheus runtime."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from adapters.inbound.http.app import create_app
from adapters.outbound.filesystem.data_dir import ensure_layout, resolve_data_dir
from adapters.outbound.filesystem.logging_setup import configure_logging
from bootstrap import __version__
from bootstrap.config import LogLevel, load_settings
from bootstrap.container import Container
from bootstrap.container_registry import VaultContainerRegistry
from domain.errors import ConfigurationError

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the runtime version and exit.",
        ),
    ] = False,
) -> None:
    """Prometheus local RAG runtime."""


def _assert_port_available(host: str, port: int) -> None:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.bind((host, port))
    except OSError as exc:
        raise RuntimeError(f"Cannot start runtime: {host}:{port} is unavailable ({exc})") from exc


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Loopback address to bind.")] = None,
    port: Annotated[int | None, typer.Option(help="TCP port to bind.")] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Directory for runtime models, indexes, state, and logs."),
    ] = None,
    session_token: Annotated[
        str | None,
        typer.Option(help="Session token expected from the plugin."),
    ] = None,
    log_level: Annotated[
        LogLevel | None,
        typer.Option(case_sensitive=False, help="Runtime log level."),
    ] = None,
) -> None:
    """Start the localhost HTTP server."""

    try:
        settings = load_settings(
            {
                "host": host,
                "port": port,
                "data_dir": data_dir,
                "session_token": session_token,
                "log_level": log_level,
            }
        )
        layout = ensure_layout(resolve_data_dir(settings.data_dir))
        configure_logging(layout, settings.log_level)
        _assert_port_available(settings.host, settings.port)
    except (ConfigurationError, RuntimeError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    container = Container(settings, layout)
    uvicorn.run(
        create_app(
            container,
            vault_registry=VaultContainerRegistry(container),
            job_store=container.job_store,
        ),
        host=settings.host,
        port=settings.port,
        log_config=None,
    )


@app.command("export-openapi")
def export_openapi(
    output: Annotated[Path | None, typer.Option(help="Output OpenAPI YAML path.")] = None,
) -> None:
    """Export the HTTP contract as JSON-compatible YAML."""

    target = output or Path(__file__).resolve().parents[4] / "contracts" / "openapi.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Run the CLI application."""

    app()
