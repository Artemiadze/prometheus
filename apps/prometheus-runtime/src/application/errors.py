"""Application-level failures with stable presentation codes."""

from domain.errors import PrometheusError


class IndexRebuildRequiredError(PrometheusError):
    """Raised when current embedding metadata is incompatible with an index."""

    code = "INDEX_REBUILD_REQUIRED"
    default_message = "Embedding configuration changed; rebuild the index before writing vectors"
