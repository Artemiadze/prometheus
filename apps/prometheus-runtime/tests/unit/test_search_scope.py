"""Tests for BR-11 search scopes."""

import pytest

from domain.errors import InvalidPathError, InvalidSearchScopeError
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import ScopeMode, SearchScope


def test_entire_vault_has_no_path_parameters() -> None:
    scope = SearchScope.entire_vault()

    assert scope.mode is ScopeMode.ENTIRE_VAULT
    assert scope.note is None
    assert scope.folders == ()


def test_current_note_requires_one_note() -> None:
    scope = SearchScope.current_note(r"Notes\Database.md")

    assert scope.note == RelativePath("Notes/Database.md")
    assert scope.folders == ()


def test_current_folder_contains_one_normalized_folder() -> None:
    scope = SearchScope.current_folder(r"Notes\Database")

    assert scope.folders == (RelativePath("Notes/Database"),)


def test_selected_folders_are_nonempty_and_deduplicated() -> None:
    scope = SearchScope.selected_folders(["University/ML", r"University\ML", "Work/Backend"])

    assert scope.folders == (
        RelativePath("University/ML"),
        RelativePath("Work/Backend"),
    )


def test_entire_vault_rejects_extra_parameters() -> None:
    with pytest.raises(InvalidSearchScopeError):
        SearchScope(ScopeMode.ENTIRE_VAULT, note=RelativePath("Note.md"))


def test_folder_modes_reject_empty_folders() -> None:
    with pytest.raises(InvalidSearchScopeError):
        SearchScope.selected_folders([])


@pytest.mark.parametrize("path", ["../Secrets", "/absolute/folder", "C:/Vault/Notes"])
def test_scope_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(InvalidPathError):
        SearchScope.current_folder(path)
