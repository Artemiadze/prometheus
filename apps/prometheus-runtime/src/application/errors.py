"""Application-level failures with stable presentation codes."""

from domain.errors import PrometheusError


class IndexRebuildRequiredError(PrometheusError):
    """Raised when current embedding metadata is incompatible with an index."""

    code = "INDEX_REBUILD_REQUIRED"
    default_message = "Embedding configuration changed; rebuild the index before writing vectors"

    def __init__(self, reason: str | None = None) -> None:
        message = self.default_message if reason is None else reason
        Exception.__init__(self, message)


class RuntimeVersionIncompatibleError(PrometheusError):
    """Raised when the Obsidian plugin version is outside the supported range."""

    code = "RUNTIME_VERSION_INCOMPATIBLE"
    default_message = "Plugin version is incompatible with this runtime"

    def __init__(self, message: str | None = None) -> None:
        Exception.__init__(self, self.default_message if message is None else message)


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


class JobNotFoundError(PrometheusError):
    code = "JOB_NOT_FOUND"
    default_message = "Background job was not found"


class DocumentTooLargeError(PrometheusError):
    code = "DOCUMENT_TOO_LARGE"
    default_message = "Document exceeds configured indexing limits"


class PathIgnoredError(PrometheusError):
    code = "PATH_IGNORED"
    default_message = "Document path is excluded from indexing"


class GroundedAnswerGenerationError(PrometheusError):
    """Raised when the language model fails to return a valid grounded answer."""

    code = "GROUNDED_ANSWER_GENERATION_FAILED"
    default_message = "Local language model returned an invalid grounded answer"
