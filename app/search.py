"""Fan-out across configured sources.

Both backends are queried concurrently and a failure in one is converted into that
source's ``error`` status, so a dead backend never blanks out the other side.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlencode

import httpx

from app.clients.audiobookshelf import AudiobookshelfClient
from app.clients.base import SearchClient, SourceError, describe_http_error
from app.clients.calibre_content_server import CalibreContentServerClient
from app.clients.calibre_web_opds import CalibreWebOpdsClient
from app.config import CalibreBackend, Settings
from app.models import SearchResponse, SourceResult, SourceStatus

logger = logging.getLogger(__name__)

AUDIOBOOKSHELF_KEY = "audiobookshelf"
CALIBRE_KEY = "calibre"
SOURCE_LABELS = {AUDIOBOOKSHELF_KEY: "Audiobookshelf", CALIBRE_KEY: "Calibre"}


def build_clients(http_client: httpx.AsyncClient, settings: Settings) -> dict[str, SearchClient]:
    """Instantiate one client per *configured* source, keyed by source key."""
    clients: dict[str, SearchClient] = {}

    if settings.audiobookshelf_enabled:
        clients[AUDIOBOOKSHELF_KEY] = AudiobookshelfClient(http_client, settings)

    match settings.resolved_calibre_backend:
        case CalibreBackend.CONTENT_SERVER:
            clients[CALIBRE_KEY] = CalibreContentServerClient(http_client, settings)
        case CalibreBackend.CALIBRE_WEB:
            clients[CALIBRE_KEY] = CalibreWebOpdsClient(http_client, settings)
        case _:
            pass

    return clients


def build_shelfmark_url(query: str, settings: Settings) -> str | None:
    """Deep link that makes Shelfmark run the same query on load."""
    if not settings.shelfmark_url:
        return None
    params = urlencode({"q": query, "content_type": settings.shelfmark_content_type.value})
    return f"{settings.shelfmark_url}/?{params}"


async def _search_one(key: str, client: SearchClient, query: str, limit: int) -> SourceResult:
    label = SOURCE_LABELS.get(key, key)
    try:
        results = await client.search(query, limit)
    except SourceError as exc:
        logger.warning("%s search failed: %s", label, exc)
        return SourceResult(key=key, label=label, status=SourceStatus.ERROR, error=str(exc))
    except Exception as exc:
        logger.exception("%s search failed unexpectedly", label)
        return SourceResult(
            key=key, label=label, status=SourceStatus.ERROR, error=describe_http_error(exc)
        )
    return SourceResult(key=key, label=label, status=SourceStatus.OK, results=results)


async def search_all(
    query: str, clients: dict[str, SearchClient], settings: Settings
) -> SearchResponse:
    """Search every configured source concurrently and collect per-source outcomes."""
    ordered_keys = [AUDIOBOOKSHELF_KEY, CALIBRE_KEY]

    tasks = {
        key: _search_one(key, clients[key], query, settings.search_limit)
        for key in ordered_keys
        if key in clients
    }
    completed = dict(zip(tasks, await asyncio.gather(*tasks.values()), strict=True))

    sources = [
        completed.get(
            key,
            SourceResult(
                key=key,
                label=SOURCE_LABELS[key],
                status=SourceStatus.DISABLED,
                error="Not configured",
            ),
        )
        for key in ordered_keys
    ]

    return SearchResponse(
        query=query, shelfmark_url=build_shelfmark_url(query, settings), sources=sources
    )
