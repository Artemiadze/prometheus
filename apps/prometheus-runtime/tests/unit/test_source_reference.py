"""Tests for navigable source references."""

import pytest

from domain.errors import InvariantViolationError
from domain.value_objects.source_reference import SourceReference

pytestmark = pytest.mark.domain


def test_link_without_heading_is_path_only() -> None:
    source = SourceReference.create("Notes/One.md")
    assert source.link == "Notes/One.md"


def test_link_with_heading_uses_obsidian_fragment() -> None:
    source = SourceReference.create(
        "Notes/One.md",
        "Topic",
        heading_line=4,
        heading_occurrence=1,
    )
    assert source.link == "Notes/One.md#Topic"


def test_heading_requires_line_and_occurrence() -> None:
    with pytest.raises(InvariantViolationError):
        SourceReference.create("Notes/One.md", "Topic")
