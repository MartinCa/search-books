"""Calibre content server (``calibre-server``) client.

Two calls: ``/ajax/search`` returns matching book ids, ``/ajax/books`` returns their
metadata. Both take an optional ``/{library_id}`` path segment for multi-library setups.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.clients.base import SearchClient, SourceError, describe_http_error
from app.config import Settings
from app.models import BookResult


class CalibreContentServerClient(SearchClient):
    key = "calibre"
    label = "Calibre"

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(client)
        self._settings = settings
        self._base_url = str(settings.calibre_url)
        self._library_id = settings.calibre_library_id

    def _path(self, endpoint: str) -> str:
        suffix = f"/{self._library_id}" if self._library_id else ""
        return f"{self._base_url}/ajax/{endpoint}{suffix}"

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        response = await self._client.get(url, params=params, auth=self._settings.calibre_auth)
        response.raise_for_status()
        return response

    async def search(self, query: str, limit: int) -> list[BookResult]:
        try:
            search_payload = (
                await self._get(
                    self._path("search"),
                    {"query": query, "num": limit, "sort": "title", "sort_order": "asc"},
                )
            ).json()

            book_ids = search_payload.get("book_ids") or []
            if not book_ids:
                return []

            books_payload = (
                await self._get(
                    self._path("books"),
                    {"ids": ",".join(str(book_id) for book_id in book_ids[:limit])},
                )
            ).json()
        except Exception as exc:
            raise SourceError(describe_http_error(exc)) from exc

        return [
            self._to_result(str(book_id), metadata)
            for book_id, metadata in books_payload.items()
            if metadata
        ]

    def _to_result(self, book_id: str, metadata: dict[str, Any]) -> BookResult:
        series_index = metadata.get("series_index")
        # Calibre stores series_index as a float; 1.0 reads better as "1".
        if isinstance(series_index, float) and series_index.is_integer():
            series_index = int(series_index)

        pubdate = metadata.get("pubdate")
        year = str(pubdate)[:4] if pubdate else None

        library_suffix = f"&library_id={self._library_id}" if self._library_id else ""

        return BookResult(
            id=book_id,
            title=metadata.get("title") or "Untitled",
            authors=list(metadata.get("authors") or []),
            series=metadata.get("series"),
            series_index=str(series_index) if series_index is not None else None,
            year=year,
            formats=sorted(fmt.upper() for fmt in metadata.get("formats") or []),
            identifiers={
                str(name): str(value) for name, value in (metadata.get("identifiers") or {}).items()
            },
            cover_url=f"/api/cover/{self.key}/{book_id}",
            item_url=f"{self._base_url}/#book_id={book_id}{library_suffix}&panel=book_details",
        )

    async def cover(self, item_id: str) -> httpx.Response:
        suffix = f"/{self._library_id}" if self._library_id else ""
        return await self._get(f"{self._base_url}/get/thumb/{item_id}{suffix}")
