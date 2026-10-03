"""A navigable source in an Obsidian Vault."""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import InvariantViolationError
from domain.value_objects.relative_path import RelativePath


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Relative note path and optional Markdown heading."""

    relative_path: RelativePath
    heading: str | None = None
    heading_line: int | None = None
    heading_occurrence: int | None = None

    def __post_init__(self) -> None:
        if self.heading is not None:
            normalized_heading = self.heading.strip() or None
            object.__setattr__(self, "heading", normalized_heading)
        if self.heading_path_fields_required():
            if self.heading_line is None or self.heading_occurrence is None:
                raise InvariantViolationError()
            if self.heading_line < 0 or self.heading_occurrence < 1:
                raise InvariantViolationError()
        elif self.heading_line is not None or self.heading_occurrence is not None:
            raise InvariantViolationError()

    def heading_path_fields_required(self) -> bool:
        return self.heading is not None

    @property
    def link(self) -> str:
        base = self.relative_path.value
        if self.heading is None:
            return base
        return f"{base}#{self.heading}"

    @classmethod
    def create(
        cls,
        relative_path: RelativePath | str,
        heading: str | None = None,
        *,
        heading_line: int | None = None,
        heading_occurrence: int | None = None,
    ) -> SourceReference:
        path = (
            relative_path
            if isinstance(relative_path, RelativePath)
            else RelativePath(relative_path)
        )
        return cls(path, heading, heading_line, heading_occurrence)
