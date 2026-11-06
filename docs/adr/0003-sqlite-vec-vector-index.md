# ADR 0003: sqlite-vec as the dense vector index

## Status

Accepted

## Context

Prometheus Runtime already persisted vault manifest and BM25 (FTS5) in
`metadata.sqlite`, while dense embeddings lived in a separate Qdrant Local
directory. That split required cross-store compensation in
`indexing_transaction`, duplicated chunk payload, and higher RAM use for
typical vault sizes (tens of thousands of chunks).

## Decision

Replace Qdrant Local with **sqlite-vec** (`vec0`) inside the same
`metadata.sqlite` file.

- Dense embeddings: `chunk_vectors` virtual table
- Chunk text and folder ancestors: relational tables used by search JOINs
- Indexing writes vectors + manifest + FTS in one `UnitOfWork` transaction
- Legacy `qdrant/` / `qdrant_metadata.json` are not migrated; full reindex is required
- `PAYLOAD_SCHEMA_VERSION` bumped to 4

## Consequences

- Simpler packaging and ops (one file per vault)
- Lower memory for desktop vaults versus Qdrant Local
- Exact KNN scales linearly; acceptable for Prometheus vault sizes
- Frozen binary must bundle the sqlite-vec native extension and load it at runtime
- Atomic reindex promote only moves `metadata.sqlite`
