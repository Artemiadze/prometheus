"""Validated retrieval scope."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from domain.errors import InvalidSearchScopeError
from domain.value_objects.relative_path import RelativePath


class ScopeMode(StrEnum):
    """Supported BR-11 search boundaries."""

    ENTIRE_VAULT = "entire_vault"
    CURRENT_NOTE = "current_note"
    CURRENT_FOLDER = "current_folder"
    SELECTED_FOLDERS = "selected_folders"


def _path(value: RelativePath | str) -> RelativePath:
    return value if isinstance(value, RelativePath) else RelativePath(value)


@dataclass(frozen=True, slots=True)
class SearchScope:
    """A mode and exactly the path parameters required by that mode."""

    mode: ScopeMode
    note: RelativePath | None = None
    folders: tuple[RelativePath, ...] = ()
    excluded_folders: tuple[RelativePath, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ScopeMode):
            raise InvalidSearchScopeError()
        unique_folders = tuple(dict.fromkeys(self.folders))
        object.__setattr__(self, "folders", unique_folders)
        unique_excluded = tuple(dict.fromkeys(self.excluded_folders))
        object.__setattr__(self, "excluded_folders", unique_excluded)

        valid = {
            ScopeMode.ENTIRE_VAULT: self.note is None and not unique_folders,
            ScopeMode.CURRENT_NOTE: self.note is not None and not unique_folders,
            ScopeMode.CURRENT_FOLDER: self.note is None and len(unique_folders) == 1,
            ScopeMode.SELECTED_FOLDERS: self.note is None and bool(unique_folders),
        }
        if not valid[self.mode]:
            raise InvalidSearchScopeError()

    @classmethod
    def entire_vault(cls) -> SearchScope:
        return cls(ScopeMode.ENTIRE_VAULT)

    @classmethod
    def current_note(cls, path: RelativePath | str) -> SearchScope:
        return cls(ScopeMode.CURRENT_NOTE, note=_path(path))

    @classmethod
    def current_folder(cls, folder: RelativePath | str) -> SearchScope:
        return cls(ScopeMode.CURRENT_FOLDER, folders=(_path(folder),))

    @classmethod
    def selected_folders(
        cls,
        folders: Iterable[RelativePath | str],
    ) -> SearchScope:
        return cls(
            ScopeMode.SELECTED_FOLDERS, folders=tuple(_path(path) for path in folders)
        )

    def with_exclusions(self, folders: Iterable[RelativePath | str]) -> SearchScope:
        merged = tuple(
            dict.fromkeys(
                (
                    *self.excluded_folders,
                    *(_path(path) for path in folders),
                )
            )
        )
        return SearchScope(
            self.mode,
            note=self.note,
            folders=self.folders,
            excluded_folders=merged,
        )
