"""Provider-independent vector-index status."""

from enum import StrEnum


class IndexStatus(StrEnum):
    """Observable health state of a Vault-scoped vector index."""

    READY = "ready"
    CORRUPTED = "index_corrupted"
