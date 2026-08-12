"""Shared client plumbing."""

from __future__ import annotations

import abc

import httpx

from app.models import BookResult


class SourceError(Exception):
    """A backend could not be searched. Surfaced to the UI as that source's error."""


class SearchClient(abc.ABC):
    """One configured backend the app can search."""

    key: str
    label: str

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @abc.abstractmethod
    async def search(self, query: str, limit: int) -> list[BookResult]:
        """Return normalized results, or raise :class:`SourceError`."""

    @abc.abstractmethod
    async def cover(self, item_id: str) -> httpx.Response:
        """Fetch a cover image for one result, authenticated as this backend requires."""


def format_series_index(value: object) -> str | None:
    """Render a series position for display: 1, 1.0 and "1.00" all become "1"."""
    if value is None or value == "":
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return str(value)
    return str(int(number)) if number.is_integer() else str(number)


def describe_http_error(exc: Exception) -> str:
    """Render an exception as a short message worth showing in the UI."""
    match exc:
        case httpx.HTTPStatusError():
            return f"HTTP {exc.response.status_code} from {exc.request.url}"
        case httpx.TimeoutException():
            return "Timed out"
        case httpx.RequestError():
            return f"Could not reach {exc.request.url}: {exc.__class__.__name__}"
        case _:
            return str(exc) or exc.__class__.__name__
