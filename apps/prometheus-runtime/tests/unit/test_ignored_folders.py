"""Tests for ignored folder value object and search scope exclusions."""

import pytest

from domain.errors import InvalidPathError
from domain.value_objects.ignored_folders import IgnoredFolders
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope

pytestmark = pytest.mark.domain


def test_system_obsidian_is_always_ignored() -> None:
    ignored = IgnoredFolders.empty()

    assert ignored.covers(RelativePath(".obsidian/plugins/x.md"))


def test_user_folder_covers_descendants() -> None:
    ignored = IgnoredFolders.from_strings(["Templates/"])

    assert ignored.covers(RelativePath("Templates/x.md"))
    assert not ignored.covers(RelativePath("Notes/x.md"))


def test_search_scope_with_exclusions_deduplicates() -> None:
    scope = SearchScope.entire_vault().with_exclusions(["Templates/", "Templates"])

    assert scope.excluded_folders == (RelativePath("Templates"),)


def test_invalid_folder_path_is_rejected() -> None:
    with pytest.raises(InvalidPathError):
        IgnoredFolders.from_strings(["../Secrets"])
