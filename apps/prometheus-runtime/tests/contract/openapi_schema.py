"""Load and validate JSON payloads against contracts/openapi.yaml schemas."""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator

_CONTRACT = Path(__file__).resolve().parents[4] / "contracts" / "openapi.yaml"


@lru_cache(maxsize=1)
def load_openapi_spec() -> dict[str, Any]:
    loaded = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("OpenAPI document must be a mapping")
    return cast(dict[str, Any], loaded)


def _resolve_refs(node: Any, schemas: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if set(node.keys()) == {"$ref"}:
            ref = str(node["$ref"])
            prefix = "#/components/schemas/"
            if not ref.startswith(prefix):
                raise ValueError(f"Unsupported schema ref: {ref}")
            return _resolve_refs(copy.deepcopy(schemas[ref[len(prefix) :]]), schemas)
        return {key: _resolve_refs(value, schemas) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(item, schemas) for item in node]
    return node


def schema_by_name(name: str) -> dict[str, Any]:
    schemas = cast(dict[str, Any], load_openapi_spec()["components"]["schemas"])
    resolved = _resolve_refs(copy.deepcopy(schemas[name]), schemas)
    return cast(dict[str, Any], resolved)


def path_response_schema(path: str, method: str, status: str) -> dict[str, Any]:
    operation = load_openapi_spec()["paths"][path][method.lower()]
    schema = operation["responses"][status]["content"]["application/json"]["schema"]
    schemas = cast(dict[str, Any], load_openapi_spec()["components"]["schemas"])
    resolved = _resolve_refs(copy.deepcopy(schema), schemas)
    return cast(dict[str, Any], resolved)


def assert_matches_schema(payload: object, schema: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


def assert_schema_named(payload: object, schema_name: str) -> None:
    assert_matches_schema(payload, schema_by_name(schema_name))
