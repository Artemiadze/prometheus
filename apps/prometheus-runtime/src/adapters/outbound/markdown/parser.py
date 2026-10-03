"""Heading-aware Markdown parser."""

from __future__ import annotations

import re
from collections.abc import Callable

from adapters.outbound.markdown.normalize import split_frontmatter
from application.dto.parsed_document import BlockKind, ParsedBlock, ParsedDocument, ParsedSection
from domain.entities.chunk import CharRange
from domain.entities.document import Document

_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_OPEN = re.compile(r"^(```+|~~~+)(.*)$")
_LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+\.)\s+")
_TABLE_ROW = re.compile(r"^\|.+\|$")
_TABLE_SEP = re.compile(r"^\|\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_QUOTE = re.compile(r"^>\s?(.*)$")


class ObsidianMarkdownParser:
    """Parse Markdown into heading sections and source-positioned blocks."""

    def parse(self, document: Document) -> ParsedDocument:
        frontmatter, source, body_start = split_frontmatter(document.content)
        if not source[body_start:].strip():
            return ParsedDocument(document.id, (), frontmatter)

        lines = _line_spans(source, body_start, len(source))
        sections = self._parse_sections(source, lines)
        return ParsedDocument(document.id, tuple(sections), frontmatter)

    def _parse_sections(
        self,
        source: str,
        lines: list[tuple[int, int, str]],
    ) -> list[ParsedSection]:
        heading_stack: list[tuple[int, str]] = []
        heading_counts: dict[str, int] = {}
        section_ordinal = 0
        current = _SectionBuilder((), 0, section_ordinal=section_ordinal)
        sections: list[ParsedSection] = []

        fence: tuple[str, int] | None = None
        fence_start = 0
        index = 0
        while index < len(lines):
            start, end, line = lines[index]
            stripped = line.strip()

            if fence is not None:
                marker, min_len = fence
                if re.match(rf"^{re.escape(marker)}{{{min_len},}}\s*$", line):
                    block_end = end if index + 1 >= len(lines) else lines[index + 1][0]
                    text = source[fence_start:block_end].rstrip("\n")
                    if text.strip():
                        current.blocks.append(
                            ParsedBlock(BlockKind.CODE, text, CharRange(fence_start, block_end))
                        )
                    fence = None
                index += 1
                continue

            if not stripped:
                index += 1
                continue

            fence_match = _FENCE_OPEN.match(line)
            if fence_match is not None:
                fence = (fence_match.group(1)[0], len(fence_match.group(1)))
                fence_start = start
                index += 1
                continue

            heading_match = _ATX_HEADING.match(line)
            if heading_match is not None:
                section = current.to_section()
                if section is not None:
                    sections.append(section)

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                heading_counts[title] = heading_counts.get(title, 0) + 1
                section_ordinal += 1
                current = _SectionBuilder(
                    tuple(title for _, title in heading_stack),
                    level,
                    section_ordinal=section_ordinal,
                    heading_line=_line_number(source, start),
                    heading_occurrence=heading_counts[title],
                )
                index += 1
                continue

            block, index = _parse_block(source, lines, index)
            if block is not None:
                current.blocks.append(block)

        if fence is not None:
            block_end = lines[-1][1]
            text = source[fence_start:block_end]
            if text.strip():
                current.blocks.append(
                    ParsedBlock(BlockKind.CODE, text, CharRange(fence_start, block_end))
                )

        section = current.to_section()
        if section is not None:
            sections.append(section)
        return sections


class _SectionBuilder:
    __slots__ = (
        "blocks",
        "heading_line",
        "heading_occurrence",
        "heading_path",
        "level",
        "section_ordinal",
    )

    def __init__(
        self,
        heading_path: tuple[str, ...],
        level: int,
        *,
        section_ordinal: int,
        heading_line: int | None = None,
        heading_occurrence: int | None = None,
    ) -> None:
        self.heading_path = heading_path
        self.level = level
        self.section_ordinal = section_ordinal
        self.heading_line = heading_line
        self.heading_occurrence = heading_occurrence
        self.blocks: list[ParsedBlock] = []

    def to_section(self) -> ParsedSection | None:
        if not self.blocks:
            return None
        return ParsedSection(
            self.heading_path,
            self.level,
            tuple(self.blocks),
            section_ordinal=self.section_ordinal,
            heading_line=self.heading_line,
            heading_occurrence=self.heading_occurrence,
        )


def _line_number(source: str, char_offset: int) -> int:
    return source[:char_offset].count("\n")


def _line_spans(source: str, start: int, end: int) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    offset = start
    while offset < end:
        line_end = source.find("\n", offset, end)
        if line_end == -1:
            line_end = end
        spans.append((offset, line_end, source[offset:line_end]))
        offset = line_end + 1 if line_end < end else end
    return spans


def _parse_block(
    source: str,
    lines: list[tuple[int, int, str]],
    index: int,
) -> tuple[ParsedBlock | None, int]:
    _, _, line = lines[index]
    if _LIST_ITEM.match(line):
        return _collect_lines(source, lines, index, _LIST_ITEM.match, BlockKind.LIST)
    if (
        _TABLE_ROW.match(line.strip())
        and index + 1 < len(lines)
        and _TABLE_SEP.match(lines[index + 1][2].strip())
    ):
        return _collect_table(source, lines, index)
    if _QUOTE.match(line):
        return _collect_lines(source, lines, index, _QUOTE.match, BlockKind.QUOTE)
    return _collect_paragraph(source, lines, index)


def _collect_lines(
    source: str,
    lines: list[tuple[int, int, str]],
    index: int,
    matcher: Callable[[str], re.Match[str] | None],
    kind: BlockKind,
) -> tuple[ParsedBlock | None, int]:
    start = lines[index][0]
    current = index
    while current < len(lines):
        _, _, line = lines[current]
        if not line.strip():
            break
        if current != index and matcher(line) is None:
            break
        current += 1
    end = lines[current - 1][1] if current > index else lines[index][1]
    text = source[start:end]
    if not text.strip():
        return None, current
    return ParsedBlock(kind, text, CharRange(start, end)), current


def _collect_table(
    source: str,
    lines: list[tuple[int, int, str]],
    index: int,
) -> tuple[ParsedBlock | None, int]:
    start = lines[index][0]
    current = index + 2
    while current < len(lines):
        _, _, line = lines[current]
        if not line.strip():
            break
        if not _TABLE_ROW.match(line.strip()):
            break
        current += 1
    end = lines[current - 1][1]
    text = source[start:end]
    if not text.strip():
        return None, current
    return ParsedBlock(BlockKind.TABLE, text, CharRange(start, end)), current


def _collect_paragraph(
    source: str,
    lines: list[tuple[int, int, str]],
    index: int,
) -> tuple[ParsedBlock | None, int]:
    start = lines[index][0]
    current = index
    while current < len(lines):
        _, _, line = lines[current]
        stripped = line.strip()
        if not stripped:
            break
        if current != index and (
            _ATX_HEADING.match(line)
            or _FENCE_OPEN.match(line)
            or _LIST_ITEM.match(line)
            or _QUOTE.match(line)
            or (
                _TABLE_ROW.match(stripped)
                and current + 1 < len(lines)
                and _TABLE_SEP.match(lines[current + 1][2].strip())
            )
        ):
            break
        current += 1
    end = lines[current - 1][1] if current > index else lines[index][1]
    text = source[start:end]
    if not text.strip():
        return None, current
    return ParsedBlock(BlockKind.PARAGRAPH, text, CharRange(start, end)), current
