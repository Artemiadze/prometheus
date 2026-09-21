# ADR 0002: Enforce Clean Architecture layer boundaries in the Obsidian plugin

- Status: Accepted
- Date: 2026-09-21

## Context

The Prometheus Obsidian plugin must keep UI, process management, and HTTP
transport out of the domain and application layers. Without automated checks,
imports of `obsidian`, `fetch`, and `child_process` can couple use cases to the
Obsidian host and local process APIs.

## Decision

Plugin dependencies point inward:

```text
bootstrap -> adapters -> application -> domain
```

`domain` and `application` must not import:

- the `obsidian` package;
- `child_process` / `node:child_process`;
- anything under `src/adapters/**`;
- the global `fetch` API.

HTTP, Vault access, and runtime process control stay behind application ports
implemented only in `adapters` and wired in `bootstrap/main.ts`.

ESLint `no-restricted-imports` and `no-restricted-globals` overrides enforce these
rules for `src/domain/**` and `src/application/**`. The plugin CI job and
`npm run lint` run the same checks locally.

## Consequences

- Use cases can be unit-tested with in-memory port fakes.
- Replacing the HTTP client or runtime spawner requires adapter and composition-root
  changes only.
- New host APIs that could leak into inner layers must be added to the restricted
  import list when introduced.
