"""Tests for domain identifier and path value objects."""

from collections.abc import Callable

import pytest

from domain.errors import InvalidIdentifierError, InvalidPathError
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.vault_id import VaultId


def test_relative_path_is_normalized_to_posix() -> None:
    assert RelativePath(r"./Notes\Database//Indexes.md").value == "Notes/Database/Indexes.md"


@pytest.mark.parametrize("value", ["", "/etc/passwd", "../Secrets.md", "C:/Vault/Note.md"])
def test_unsafe_relative_path_is_rejected(value: str) -> None:
    with pytest.raises(InvalidPathError):
        RelativePath(value)


def test_document_id_is_deterministic_for_normalized_path() -> None:
    first = DocumentId.from_relative_path("Notes/Database.md")
    second = DocumentId.from_relative_path(r"./Notes\Database.md")

    assert first == second
    assert hash(first) == hash(second)


def test_document_id_can_be_supplied_as_stable_opaque_id() -> None:
    assert DocumentId("plugin-document-01").value == "plugin-document-01"


def test_chunk_id_is_deterministic() -> None:
    document_id = DocumentId.from_relative_path("Notes/Database.md")

    first = ChunkId.from_parts(document_id, ("Database", "Indexes"), 2)
    second = ChunkId.from_parts(document_id, ("Database", "Indexes"), 2)

    assert first == second
    assert first != ChunkId.from_parts(document_id, ("Database", "Indexes"), 3)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: VaultId("../vault"),
        lambda: VaultId("SHORT"),
        lambda: DocumentId("../document"),
        lambda: ChunkId("bad/id"),
        lambda: ChunkId.from_parts(DocumentId("document-01"), (), -1),
    ],
)
def test_invalid_identifiers_raise_domain_error(factory: Callable[[], object]) -> None:
    with pytest.raises(InvalidIdentifierError):
        factory()


def test_identifiers_are_hashable() -> None:
    vault_id = VaultId("vault-01")
    document_id = DocumentId("document-01")

    values = {vault_id: "vault", document_id: "document"}

    assert values[vault_id] == "vault"
    assert values[document_id] == "document"
