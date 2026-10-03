"""HTTP schemas for semantic search."""

from typing import Literal

from pydantic import Field, model_validator

from adapters.inbound.http.schemas.common import ApiSchema
from application.dto.search_result import SearchResult
from domain.value_objects.search_scope import SearchScope


class SearchScopeRequest(ApiSchema):
    mode: Literal["entire_vault", "current_note", "current_folder", "selected_folders"]
    note: str | None = None
    folders: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_shape(self) -> "SearchScopeRequest":
        if self.mode == "current_note" and self.note is None:
            raise ValueError("note is required for current_note scope")
        if self.mode in {"current_folder", "selected_folders"} and not self.folders:
            raise ValueError("folders are required for folder scope")
        return self

    def to_domain(self) -> SearchScope:
        if self.mode == "entire_vault":
            return SearchScope.entire_vault()
        if self.mode == "current_note":
            assert self.note is not None
            return SearchScope.current_note(self.note)
        if self.mode == "current_folder":
            return SearchScope.current_folder(self.folders[0])
        return SearchScope.selected_folders(self.folders)


class SearchRequest(ApiSchema):
    query: str = Field(examples=["How does vector search work?"])
    limit: int = Field(default=10, gt=0, le=100)
    scope: SearchScopeRequest | None = None


class SearchResultResponse(ApiSchema):
    path: str
    heading: str | None
    text: str
    score: float
    link: str
    heading_line: int | None = None
    heading_occurrence: int | None = None

    @classmethod
    def from_dto(cls, result: SearchResult) -> "SearchResultResponse":
        return cls(
            path=result.relative_path.value,
            heading=result.heading,
            text=result.text,
            score=result.score,
            link=result.link,
            heading_line=result.heading_line,
            heading_occurrence=result.heading_occurrence,
        )


class SearchResponse(ApiSchema):
    results: tuple[SearchResultResponse, ...]
