"""Application-level failures with stable presentation codes."""

from domain.errors import PrometheusError


class IndexRebuildRequiredError(PrometheusError):
    """Raised when current embedding metadata is incompatible with an index."""

    code = "INDEX_REBUILD_REQUIRED"
    default_message = "Embedding configuration changed; rebuild the index before writing vectors"


class IndexCorruptedError(PrometheusError):
    """Raised when a recreated index still requires a full reindex."""

    code = "INDEX_CORRUPTED"
    default_message = "Vector index was corrupted or incompatible; reindex the Vault"


class VaultNotIndexedError(PrometheusError):
    code = "VAULT_NOT_INDEXED"
    default_message = "Vault has not been indexed"


class QueryTooShortError(PrometheusError):
    code = "QUERY_TOO_SHORT"
    default_message = "Search query is too short"


class RevisionConflictError(PrometheusError):
    code = "REVISION_CONFLICT"
    default_message = "Document revision is older than the indexed revision"


class VaultMismatchError(PrometheusError):
    code = "VAULT_MISMATCH"
    default_message = "Document belongs to a different Vault"
