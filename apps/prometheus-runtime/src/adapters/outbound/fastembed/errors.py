"""Safe failures exposed by the FastEmbed adapter."""

from domain.errors import PrometheusError


class EmbeddingModelUnavailableError(PrometheusError):
    """Raised when the selected model cannot be opened from the allowed sources."""

    code = "EMBEDDING_MODEL_UNAVAILABLE"
    default_message = "The selected embedding model is unavailable"


class EmbeddingBatchError(PrometheusError):
    """Raised when one embedding batch fails without exposing its text."""

    code = "EMBEDDING_BATCH_FAILED"
    default_message = "Embedding batch failed"

    def __init__(self, batch_index: int, processed_count: int) -> None:
        self.batch_index = batch_index
        self.processed_count = processed_count
        super().__init__()


class EmbeddingDimensionMismatchError(PrometheusError):
    """Raised when FastEmbed returns a vector with an unexpected dimension."""

    code = "EMBEDDING_DIMENSION_MISMATCH"
    default_message = "Embedding vector dimension does not match model metadata"

    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__()
