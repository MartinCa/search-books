"""Calibre-Web client, via its OPDS catalog.

Calibre-Web has no JSON search API, but ``GET /opds/search?query=`` returns an Atom feed
with one ``<entry>`` per book, acquisition links per format and a cover link.
"""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree

import httpx

from app.clients.base import SearchClient, SourceError, describe_http_error
from app.config import Settings
from app.models import BookResult

ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/terms/}"
ACQUISITION_REL = "http://opds-spec.org/acquisition"

_ID_PATTERN = re.compile(r"(\d+)")


class CalibreWebOpdsClient(SearchClient):
    key = "calibre"
    label = "Calibre"

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(client)
        self._settings = settings
        self._base_url = str(settings.calibre_url)

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        response = await self._client.get(url, params=params, auth=self._settings.calibre_auth)
        response.raise_for_status()
        return response

    async def search(self, query: str, limit: int) -> list[BookResult]:
        try:
            response = await self._get(f"{self._base_url}/opds/search", {"query": query})
            feed = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise SourceError(f"Invalid OPDS feed: {exc}") from exc
        except Exception as exc:
            raise SourceError(describe_http_error(exc)) from exc

        entries = feed.findall(f"{ATOM}entry")
        return [self._to_result(entry) for entry in entries[:limit]]

    def _to_result(self, entry: ElementTree.Element) -> BookResult:
        formats: list[str] = []
        cover_url: str | None = None

        for link in entry.findall(f"{ATOM}link"):
            rel = link.get("rel") or ""
            href = link.get("href") or ""
            if rel.startswith(ACQUISITION_REL):
                # /opds/download/{book_id}/{format}/ -- the path carries the format.
                parts = [part for part in href.split("/") if part]
                if parts:
                    formats.append(parts[-1].upper())
            elif rel in {"http://opds-spec.org/image", "http://opds-spec.org/cover"}:
                cover_url = href

        book_id = self._entry_id(entry)
        published = entry.findtext(f"{DC}issued") or entry.findtext(f"{ATOM}published")

        return BookResult(
            id=book_id,
            title=(entry.findtext(f"{ATOM}title") or "Untitled").strip(),
            authors=[
                name.strip()
                for author in entry.findall(f"{ATOM}author")
                if (name := author.findtext(f"{ATOM}name"))
            ],
            series=entry.findtext(f"{DC}series"),
            year=published[:4] if published else None,
            formats=sorted(set(formats)),
            cover_url=f"/api/cover/{self.key}/{book_id}" if cover_url else None,
            item_url=f"{self._base_url}/book/{book_id}" if book_id else None,
        )

    @staticmethod
    def _entry_id(entry: ElementTree.Element) -> str:
        """Pull the numeric Calibre id out of the entry, falling back to the raw id."""
        raw = entry.findtext(f"{ATOM}id") or ""
        for link in entry.findall(f"{ATOM}link"):
            if (link.get("rel") or "").startswith(ACQUISITION_REL):
                parts = [part for part in (link.get("href") or "").split("/") if part]
                # /opds/download/{book_id}/{format}/
                if len(parts) >= 2 and parts[-2].isdigit():
                    return parts[-2]
        match = _ID_PATTERN.search(raw)
        return match.group(1) if match else raw.strip()

    async def cover(self, item_id: str) -> httpx.Response:
        return await self._get(f"{self._base_url}/opds/cover/{item_id}")
