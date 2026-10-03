"""Vault paths excluded from indexing and retrieval."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from domain.value_objects.relative_path import RelativePath

_SYSTEM_IGNORED = (RelativePath(".obsidian"),)


@dataclass(frozen=True, slots=True)
class IgnoredFolders:
    """Normalized folder prefixes that must never be indexed or retrieved."""

    folders: tuple[RelativePath, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        unique: list[RelativePath] = []
        for folder in (*_SYSTEM_IGNORED, *self.folders):
            if folder.value in seen:
                continue
            seen.add(folder.value)
            unique.append(folder)
        object.__setattr__(self, "folders", tuple(unique))

    @classmethod
    def empty(cls) -> IgnoredFolders:
        return cls(())

    @classmethod
    def from_strings(cls, folders: Iterable[str]) -> IgnoredFolders:
        return cls(tuple(RelativePath(value) for value in folders))

    def covers(self, path: RelativePath) -> bool:
        return any(_path_under_folder(path, folder) for folder in self.folders)

    def as_relative_paths(self) -> tuple[RelativePath, ...]:
        return self.folders


def _path_under_folder(path: RelativePath, folder: RelativePath) -> bool:
    if path == folder:
        return True
    prefix = f"{folder.value}/"
    return path.value.startswith(prefix)
