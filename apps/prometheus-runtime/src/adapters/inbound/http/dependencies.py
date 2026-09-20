"""FastAPI dependencies that resolve Vault-scoped runtime services."""

from __future__ import annotations

from typing import Protocol, cast

from fastapi import Request

from application.ports.job_store import JobStore
from application.ports.language_model import LanguageModel
from application.use_cases.answer_question import AnswerQuestion
from application.use_cases.get_runtime_status import GetRuntimeStatus
from application.use_cases.index_document import IndexDocument
from application.use_cases.reindex_vault import ReindexVault
from application.use_cases.remove_document import RemoveDocument
from application.use_cases.search_notes import SearchNotes
from application.use_cases.synchronize_vault import SynchronizeVault
from domain.value_objects.vault_id import VaultId


class SessionToken(Protocol):
    def get_secret_value(self) -> str: ...


class Settings(Protocol):
    session_token: SessionToken | None


class BaseRuntime(Protocol):
    settings: Settings
    language_model: LanguageModel
    job_store: JobStore


class VaultRuntime(Protocol):
    index_document: IndexDocument
    remove_document: RemoveDocument
    synchronize_vault: SynchronizeVault
    search_notes: SearchNotes
    answer_question: AnswerQuestion
    reindex_vault: ReindexVault
    runtime_status: GetRuntimeStatus


class VaultRegistry(Protocol):
    def get(self, vault_id: VaultId) -> VaultRuntime: ...


def get_base_container(request: Request) -> BaseRuntime:
    container = request.app.state.container
    if not hasattr(container, "settings"):
        raise RuntimeError("HTTP application has no configured Container")
    return cast(BaseRuntime, container)


def get_registry(request: Request) -> VaultRegistry:
    registry = request.app.state.vault_registry
    if not hasattr(registry, "get"):
        raise RuntimeError("HTTP application has no configured VaultContainerRegistry")
    return cast(VaultRegistry, registry)


def get_vault_container(request: Request, vault_id: str) -> VaultRuntime:
    return get_registry(request).get(VaultId(vault_id))
