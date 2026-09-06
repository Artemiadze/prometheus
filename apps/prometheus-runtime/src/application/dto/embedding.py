"""Provider-independent embedding metadata."""

from dataclasses import dataclass

from domain.errors import InvariantViolationError


@dataclass(frozen=True, slots=True)
class EmbeddingFingerprint:
    """Index-relevant identity of one embedding model."""

    provider: str
    model_id: str
    dimension: int

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model_id.strip() or self.dimension <= 0:
            raise InvariantViolationError()
