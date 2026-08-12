"""Calibre-Web client, via its OPDS catalog.

Calibre-Web has no JSON search API, but ``GET /opds/search?query=`` returns an Atom feed
with one ``<entry>`` per book. The shapes handled here follow Calibre-Web's own
``cps/templates/feed.xml``:

* ``<id>`` is ``urn:uuid:<uuid>`` -- it does **not** carry the Calibre book id, so the id
  is recovered from an acquisition link (``/opds/download/{book_id}/{format}/``) instead.
* series is not exposed as an element; the template renders it into the xhtml ``<content>``
  block as ``SERIES: <name> [<index>]``.
* dates come from ``<published>``.
"""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree

import httpx

from app.clients.base import (
    SearchClient,
    SourceError,
    describe_http_error,
    format_series_index,
)
from app.config import Settings
from app.models import BookResult

ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/terms/}"
ACQUISITION_REL = "http://opds-spec.org/acquisition"
COVER_RELS = frozenset({"http://opds-spec.org/image", "http://opds-spec.org/cover"})

_SERIES_PATTERN = re.compile(r"SERIES:\s*(?P<name>.+?)\s*\[(?P<index>[\d.]+)\]")


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
        book_id = ""
        has_cover = False

        for link in entry.findall(f"{ATOM}link"):
            rel = link.get("rel") or ""
            if rel in COVER_RELS:
                has_cover = True
                continue
            if not rel.startswith(ACQUISITION_REL):
                continue

            # /opds/download/{book_id}/{format}/
            parts = [part for part in (link.get("href") or "").split("/") if part]
            # The link's title is the format name already ("EPUB"); the path is the fallback.
            formats.append((link.get("title") or (parts[-1] if parts else "")).upper())
            if not book_id and len(parts) >= 2 and parts[-2].isdigit():
                book_id = parts[-2]

        series, series_index = self._series(entry)
        published = entry.findtext(f"{DC}issued") or entry.findtext(f"{ATOM}published")

        return BookResult(
            id=book_id,
            title=(entry.findtext(f"{ATOM}title") or "Untitled").strip(),
            authors=[
                name.strip()
                for author in entry.findall(f"{ATOM}author")
                if (name := author.findtext(f"{ATOM}name"))
            ],
            series=series,
            series_index=series_index,
            year=published[:4] if published else None,
            formats=sorted({fmt for fmt in formats if fmt}),
            # Without a book id there is nothing to link to: the entry id is a UUID, and
            # guessing an id from it would silently point at some other book.
            cover_url=f"/api/cover/{self.key}/{book_id}" if has_cover and book_id else None,
            item_url=f"{self._base_url}/book/{book_id}" if book_id else None,
        )

    @staticmethod
    def _series(entry: ElementTree.Element) -> tuple[str | None, str | None]:
        """Recover series from the xhtml content block, where the template renders it."""
        content = entry.find(f"{ATOM}content")
        if content is None:
            return None, None

        match = _SERIES_PATTERN.search("".join(content.itertext()))
        if match is None:
            return None, None
        return match["name"], format_series_index(match["index"])

    async def cover(self, item_id: str) -> httpx.Response:
        return await self._get(f"{self._base_url}/opds/cover/{item_id}")
