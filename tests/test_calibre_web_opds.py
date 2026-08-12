from __future__ import annotations

import httpx
import pytest
import respx

from app.clients.base import SourceError
from app.clients.calibre_web_opds import CalibreWebOpdsClient
from app.config import Settings
from tests.conftest import load_bytes

EMPTY_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Search</title></feed>"""


@respx.mock
async def test_atom_entries_become_results(
    http_client: httpx.AsyncClient, calibre_web_settings: Settings
) -> None:
    route = respx.get("https://cw.example.com/opds/search").mock(
        return_value=httpx.Response(
            200,
            content=load_bytes("opds_search.xml"),
            headers={"content-type": "application/atom+xml"},
        )
    )

    results = await CalibreWebOpdsClient(http_client, calibre_web_settings).search("goodkind", 25)

    assert route.calls.last.request.url.params["query"] == "goodkind"
    assert len(results) == 2

    first = results[0]
    assert first.id == "12"
    assert first.title == "Wizard's First Rule"
    assert first.authors == ["Terry Goodkind"]
    assert first.series == "Sword of Truth"
    assert first.year == "1994"
    assert first.formats == ["EPUB", "MOBI"], "one format per acquisition link"
    assert first.cover_url == "/api/cover/calibre/12"
    assert first.item_url == "https://cw.example.com/book/12"

    second = results[1]
    assert second.authors == ["Terry Goodkind", "Somebody Else"]
    assert second.cover_url is None, "no image link means no cover"
    assert second.year is None


@respx.mock
async def test_empty_feed_yields_no_results(
    http_client: httpx.AsyncClient, calibre_web_settings: Settings
) -> None:
    respx.get("https://cw.example.com/opds/search").mock(
        return_value=httpx.Response(200, content=EMPTY_FEED)
    )

    assert await CalibreWebOpdsClient(http_client, calibre_web_settings).search("x", 25) == []


@respx.mock
async def test_results_are_capped_at_the_limit(
    http_client: httpx.AsyncClient, calibre_web_settings: Settings
) -> None:
    respx.get("https://cw.example.com/opds/search").mock(
        return_value=httpx.Response(200, content=load_bytes("opds_search.xml"))
    )

    results = await CalibreWebOpdsClient(http_client, calibre_web_settings).search("x", 1)

    assert len(results) == 1


@respx.mock
async def test_malformed_xml_becomes_source_error(
    http_client: httpx.AsyncClient, calibre_web_settings: Settings
) -> None:
    respx.get("https://cw.example.com/opds/search").mock(
        return_value=httpx.Response(200, content=b"<feed><entry>")
    )

    with pytest.raises(SourceError, match="Invalid OPDS feed"):
        await CalibreWebOpdsClient(http_client, calibre_web_settings).search("x", 25)


@respx.mock
async def test_http_error_becomes_source_error(
    http_client: httpx.AsyncClient, calibre_web_settings: Settings
) -> None:
    respx.get("https://cw.example.com/opds/search").mock(return_value=httpx.Response(401))

    with pytest.raises(SourceError, match="HTTP 401"):
        await CalibreWebOpdsClient(http_client, calibre_web_settings).search("x", 25)


@respx.mock
async def test_basic_auth_is_sent_when_configured(http_client: httpx.AsyncClient) -> None:
    settings = Settings(
        calibre_backend="calibre-web",
        calibre_url="https://cw.example.com",
        calibre_username="user",
        calibre_password="pass",
    )
    route = respx.get("https://cw.example.com/opds/search").mock(
        return_value=httpx.Response(200, content=EMPTY_FEED)
    )

    await CalibreWebOpdsClient(http_client, settings).search("x", 25)

    assert route.calls.last.request.headers["Authorization"].startswith("Basic ")


@respx.mock
async def test_cover_uses_the_opds_cover_endpoint(
    http_client: httpx.AsyncClient, calibre_web_settings: Settings
) -> None:
    route = respx.get("https://cw.example.com/opds/cover/12").mock(
        return_value=httpx.Response(200, content=b"img")
    )

    response = await CalibreWebOpdsClient(http_client, calibre_web_settings).cover("12")

    assert route.called
    assert response.content == b"img"
