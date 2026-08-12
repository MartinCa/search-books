from __future__ import annotations

import base64

import httpx
import pytest
import respx

from app.clients.base import SourceError
from app.clients.calibre_content_server import CalibreContentServerClient
from app.config import Settings
from tests.conftest import load_json


@respx.mock
async def test_search_uses_two_calls_and_maps_metadata(
    http_client: httpx.AsyncClient, calibre_settings: Settings
) -> None:
    search = respx.get("https://calibre.example.com/ajax/search").mock(
        return_value=httpx.Response(200, json={"book_ids": [12, 13], "total_num": 2})
    )
    books = respx.get("https://calibre.example.com/ajax/books").mock(
        return_value=httpx.Response(200, json=load_json("calibre_books.json"))
    )

    results = await CalibreContentServerClient(http_client, calibre_settings).search("goodkind", 25)

    assert search.calls.last.request.url.params["query"] == "goodkind"
    assert search.calls.last.request.url.params["num"] == "25"
    assert books.calls.last.request.url.params["ids"] == "12,13"

    first = results[0]
    assert first.title == "Wizard's First Rule"
    assert first.authors == ["Terry Goodkind"]
    assert first.series == "Sword of Truth"
    assert first.series_index == "1", "a whole-number series index loses its .0"
    assert first.year == "1994"
    assert first.formats == ["EPUB", "MOBI"]
    assert first.identifiers == {"isbn": "9780812548051"}
    assert first.cover_url == "/api/cover/calibre/12"
    assert "book_id=12" in first.item_url

    second = results[1]
    assert second.series_index == "2.5", "a fractional series index is kept as-is"
    assert second.year is None


@respx.mock
async def test_empty_search_skips_the_metadata_call(
    http_client: httpx.AsyncClient, calibre_settings: Settings
) -> None:
    respx.get("https://calibre.example.com/ajax/search").mock(
        return_value=httpx.Response(200, json={"book_ids": []})
    )
    books = respx.get("https://calibre.example.com/ajax/books")

    results = await CalibreContentServerClient(http_client, calibre_settings).search("nothing", 25)

    assert results == []
    assert not books.called


@respx.mock
async def test_library_id_is_added_to_both_paths(http_client: httpx.AsyncClient) -> None:
    settings = Settings(
        calibre_backend="content-server",
        calibre_url="https://calibre.example.com",
        calibre_library_id="Fiction",
    )
    respx.get("https://calibre.example.com/ajax/search/Fiction").mock(
        return_value=httpx.Response(200, json={"book_ids": [12]})
    )
    books = respx.get("https://calibre.example.com/ajax/books/Fiction").mock(
        return_value=httpx.Response(200, json={"12": load_json("calibre_books.json")["12"]})
    )

    results = await CalibreContentServerClient(http_client, settings).search("x", 25)

    assert books.called
    assert "library_id=Fiction" in results[0].item_url


@respx.mock
async def test_basic_auth_is_sent_when_configured(http_client: httpx.AsyncClient) -> None:
    settings = Settings(
        calibre_backend="content-server",
        calibre_url="https://calibre.example.com",
        calibre_username="user",
        calibre_password="pass",
    )
    route = respx.get("https://calibre.example.com/ajax/search").mock(
        return_value=httpx.Response(200, json={"book_ids": []})
    )

    await CalibreContentServerClient(http_client, settings).search("x", 25)

    expected = base64.b64encode(b"user:pass").decode()
    assert route.calls.last.request.headers["Authorization"] == f"Basic {expected}"


@respx.mock
async def test_ids_are_capped_at_the_limit(
    http_client: httpx.AsyncClient, calibre_settings: Settings
) -> None:
    respx.get("https://calibre.example.com/ajax/search").mock(
        return_value=httpx.Response(200, json={"book_ids": list(range(1, 20))})
    )
    books = respx.get("https://calibre.example.com/ajax/books").mock(
        return_value=httpx.Response(200, json={})
    )

    await CalibreContentServerClient(http_client, calibre_settings).search("x", 3)

    assert books.calls.last.request.url.params["ids"] == "1,2,3"


@respx.mock
async def test_null_metadata_entries_are_dropped(
    http_client: httpx.AsyncClient, calibre_settings: Settings
) -> None:
    respx.get("https://calibre.example.com/ajax/search").mock(
        return_value=httpx.Response(200, json={"book_ids": [12, 99]})
    )
    respx.get("https://calibre.example.com/ajax/books").mock(
        return_value=httpx.Response(
            200, json={"12": load_json("calibre_books.json")["12"], "99": None}
        )
    )

    results = await CalibreContentServerClient(http_client, calibre_settings).search("x", 25)

    assert [book.id for book in results] == ["12"]


@respx.mock
async def test_http_error_becomes_source_error(
    http_client: httpx.AsyncClient, calibre_settings: Settings
) -> None:
    respx.get("https://calibre.example.com/ajax/search").mock(return_value=httpx.Response(502))

    with pytest.raises(SourceError, match="HTTP 502"):
        await CalibreContentServerClient(http_client, calibre_settings).search("x", 25)


@respx.mock
async def test_cover_uses_the_thumb_endpoint(
    http_client: httpx.AsyncClient, calibre_settings: Settings
) -> None:
    route = respx.get("https://calibre.example.com/get/thumb/12").mock(
        return_value=httpx.Response(200, content=b"img")
    )

    response = await CalibreContentServerClient(http_client, calibre_settings).cover("12")

    assert route.called
    assert response.content == b"img"
