"""Vault-scoped document indexing routes."""

from fastapi import APIRouter, Depends, Request

from adapters.inbound.http.auth import require_session_token
from adapters.inbound.http.dependencies import get_vault_container
from adapters.inbound.http.schemas.common import ERROR_RESPONSES
from adapters.inbound.http.schemas.documents import (
    DocumentUpsertRequest,
    IndexDocumentResponse,
    RemoveDocumentResponse,
)
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId

router = APIRouter(
    prefix="/v1/vaults/{vault_id}/documents",
    dependencies=[Depends(require_session_token)],
)


@router.put(
    "/{document_id}",
    response_model=IndexDocumentResponse,
    responses=ERROR_RESPONSES,
)
async def put_document(
    request: Request,
    vault_id: str,
    document_id: str,
    body: DocumentUpsertRequest,
) -> IndexDocumentResponse:
    vault = VaultId(vault_id)
    document = body.to_domain(vault, DocumentId(document_id))
    result = await get_vault_container(request, vault_id).index_document.execute(document)
    return IndexDocumentResponse.from_dto(result)


@router.delete(
    "/{document_id}",
    response_model=RemoveDocumentResponse,
    responses=ERROR_RESPONSES,
)
async def delete_document(
    request: Request,
    vault_id: str,
    document_id: str,
) -> RemoveDocumentResponse:
    result = await get_vault_container(request, vault_id).remove_document.execute(
        DocumentId(document_id)
    )
    return RemoveDocumentResponse.from_dto(result)
