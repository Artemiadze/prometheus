"""HTTP schemas for runtime and local-model status."""

from datetime import datetime

from adapters.inbound.http.schemas.common import ApiSchema
from application.dto.llm import LocalLlmModel
from application.dto.runtime_status import RuntimeStatus


class StatusResponse(ApiSchema):
    runtime_version: str
    api_version: str
    index_state: str
    llm_available: bool
    llm_model: str
    document_count: int
    chunk_count: int
    last_indexed_at: datetime | None
    index_size_bytes: int

    @classmethod
    def from_dto(cls, status: RuntimeStatus, api_version: str) -> "StatusResponse":
        return cls(
            runtime_version=status.runtime_version,
            api_version=api_version,
            index_state=status.index_state.value,
            llm_available=status.llm_available,
            llm_model=status.llm_model,
            document_count=status.document_count,
            chunk_count=status.chunk_count,
            last_indexed_at=status.last_indexed_at,
            index_size_bytes=status.index_size_bytes,
        )


class ModelResponse(ApiSchema):
    name: str
    size_bytes: int
    quantization: str | None

    @classmethod
    def from_dto(cls, model: LocalLlmModel) -> "ModelResponse":
        return cls(name=model.name, size_bytes=model.size_bytes, quantization=model.quantization)


class ModelsResponse(ApiSchema):
    models: tuple[ModelResponse, ...]
