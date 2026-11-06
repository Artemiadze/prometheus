# ADR 0001: Enforce Clean Architecture layer boundaries

- Status: Accepted
- Date: 2026-09-05

## Context

Prometheus Runtime must keep business rules independent from FastAPI, persistence,
embedding, vector-store, and HTTP client libraries. Without automated checks, imports
from these libraries can gradually couple use cases to infrastructure.

## Decision

Runtime dependencies point inward:

```text
bootstrap -> adapters -> application -> domain
```

`domain` imports neither another runtime layer nor framework/IO packages.
`application` imports only `domain` and the standard library. Ports are `Protocol`
types owned by `application`; adapter-specific request and response types do not cross
that boundary. `adapters` implement ports, and `bootstrap` is the only composition root.

Import Linter enforces both the layer order and explicit bans on FastAPI, Uvicorn,
HTTPX, FastEmbed, sqlite drivers/extensions, and pydantic-settings in inner layers. The `make arch`
target runs these contracts locally and in CI.

## Consequences

- Use cases can be unit-tested with in-memory port implementations.
- Replacing infrastructure requires changes in adapters and the composition root only.
- Transport and persistence models require explicit mapping at adapter boundaries.
- New external framework packages must be added to the forbidden contracts when they
  could leak into inner layers.
