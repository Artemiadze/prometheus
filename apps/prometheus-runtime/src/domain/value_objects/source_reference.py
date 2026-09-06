"""A navigable source in an Obsidian Vault."""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.relative_path import RelativePath


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Relative note path and optional Markdown heading."""

    relative_path: RelativePath
    heading: str | None = None

    def __post_init__(self) -> None:
        if self.heading is not None:
            normalized_heading = self.heading.strip() or None
            object.__setattr__(self, "heading", normalized_heading)

    @classmethod
    def create(
        cls,
        relative_path: RelativePath | str,
        heading: str | None = None,
    ) -> SourceReference:
        path = (
            relative_path
            if isinstance(relative_path, RelativePath)
            else RelativePath(relative_path)
        )
        return cls(path, heading)
