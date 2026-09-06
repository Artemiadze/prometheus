"""Safe normalized paths relative to an Obsidian Vault."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from domain.errors import InvalidPathError

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:/")


@dataclass(frozen=True, slots=True)
class RelativePath:
    """A normalized POSIX path that cannot escape its Vault."""

    value: str

    def __post_init__(self) -> None:
        raw = self.value.replace("\\", "/")
        if not raw or "\x00" in raw or raw.startswith("/") or _WINDOWS_DRIVE.match(raw):
            raise InvalidPathError()

        parts = tuple(part for part in raw.split("/") if part not in {"", "."})
        if not parts or ".." in parts:
            raise InvalidPathError()

        normalized = PurePosixPath(*parts).as_posix()
        object.__setattr__(self, "value", normalized)

    @property
    def name(self) -> str:
        return PurePosixPath(self.value).name

    @property
    def parent(self) -> RelativePath | None:
        parent = PurePosixPath(self.value).parent.as_posix()
        return None if parent == "." else RelativePath(parent)

    def __str__(self) -> str:
        return self.value
