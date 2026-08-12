"""Normalized shapes both backends map into, so the UI renders one card type."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class SourceStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    DISABLED = "disabled"


class BookResult(BaseModel):
    """A single book, however it was found."""

    id: str
    title: str
    subtitle: str | None = None
    authors: list[str] = Field(default_factory=list)
    series: str | None = None
    series_index: str | None = None
    year: str | None = None
    formats: list[str] = Field(default_factory=list)
    narrators: list[str] = Field(default_factory=list)
    identifiers: dict[str, str] = Field(default_factory=dict)
    cover_url: str | None = None
    item_url: str | None = None


class SourceResult(BaseModel):
    """Per-source outcome. A failure here is data, not an HTTP error."""

    key: str
    label: str
    status: SourceStatus
    error: str | None = None
    results: list[BookResult] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def count(self) -> int:
        return len(self.results)


class SearchResponse(BaseModel):
    query: str
    shelfmark_url: str | None = None
    sources: list[SourceResult] = Field(default_factory=list)
