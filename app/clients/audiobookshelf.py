"""Audiobookshelf client.

Uses ``GET /api/libraries`` to discover libraries and
``GET /api/libraries/{id}/search?q=&limit=`` for the query itself. The API token is sent
as a Bearer header and never leaves the server -- covers are proxied by the app.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.clients.base import (
    SearchClient,
    SourceError,
    describe_http_error,
    format_series_index,
)
from app.config import Settings
from app.models import BookResult


class AudiobookshelfClient(SearchClient):
    key = "audiobookshelf"
    label = "Audiobookshelf"

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(client)
        self._settings = settings
        self._base_url = str(settings.audiobookshelf_url)
        self._library_ids: list[str] | None = None

    @property
    def _headers(self) -> dict[str, str]:
        if self._settings.audiobookshelf_token:
            return {"Authorization": f"Bearer {self._settings.audiobookshelf_token}"}
        return {}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        response = await self._client.get(
            f"{self._base_url}{path}", params=params, headers=self._headers
        )
        response.raise_for_status()
        return response

    async def _resolve_library_ids(self) -> list[str]:
        """List the libraries to search, cached for the process lifetime."""
        if self._settings.audiobookshelf_library_ids:
            return self._settings.audiobookshelf_library_ids
        if self._library_ids is not None:
            return self._library_ids

        payload = (await self._get("/api/libraries")).json()
        wanted = {"book"}
        if self._settings.audiobookshelf_include_podcasts:
            wanted.add("podcast")
        self._library_ids = [
            library["id"]
            for library in payload.get("libraries", [])
            if library.get("mediaType", "book") in wanted
        ]
        return self._library_ids

    async def search(self, query: str, limit: int) -> list[BookResult]:
        try:
            library_ids = await self._resolve_library_ids()
            if not library_ids:
                return []

            responses = await asyncio.gather(
                *(
                    self._get(f"/api/libraries/{library_id}/search", {"q": query, "limit": limit})
                    for library_id in library_ids
                )
            )
        except Exception as exc:
            raise SourceError(describe_http_error(exc)) from exc

        results: list[BookResult] = []
        seen: set[str] = set()
        for response in responses:
            payload = response.json()
            # The item key is `book` or `podcast` depending on the library's media type.
            for key in ("book", "podcast"):
                for hit in payload.get(key) or []:
                    item = hit.get("libraryItem") or {}
                    if not item.get("id") or item["id"] in seen:
                        continue
                    seen.add(item["id"])
                    results.append(self._to_result(item))

        return results[:limit]

    def _to_result(self, item: dict[str, Any]) -> BookResult:
        metadata = (item.get("media") or {}).get("metadata") or {}

        identifiers = {name: str(metadata[name]) for name in ("isbn", "asin") if metadata.get(name)}
        narrators = metadata.get("narrators") or []
        if not narrators and metadata.get("narratorName"):
            narrators = [metadata["narratorName"]]

        series = metadata.get("series") or []
        series_name = series[0].get("name") if series else metadata.get("seriesName") or None
        series_index = series[0].get("sequence") if series else None

        authors = [author["name"] for author in metadata.get("authors") or [] if author.get("name")]
        if not authors and metadata.get("authorName"):
            authors = [metadata["authorName"]]

        published = metadata.get("publishedYear")
        return BookResult(
            id=item["id"],
            title=metadata.get("title") or "Untitled",
            subtitle=metadata.get("subtitle"),
            authors=authors,
            series=series_name,
            series_index=format_series_index(series_index),
            year=str(published) if published else None,
            formats=sorted(
                {
                    audio_file["metadata"]["ext"].lstrip(".").upper()
                    for audio_file in (item.get("media") or {}).get("audioFiles") or []
                    if (audio_file.get("metadata") or {}).get("ext")
                }
            ),
            narrators=narrators,
            identifiers=identifiers,
            cover_url=f"/api/cover/{self.key}/{item['id']}",
            item_url=f"{self._base_url}/item/{item['id']}",
        )

    async def cover(self, item_id: str) -> httpx.Response:
        return await self._get(f"/api/items/{item_id}/cover")
