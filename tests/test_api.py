from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager

from app.config import Settings
from app.main import create_app
from tests.conftest import load_json

ALL_SOURCES = Settings(
    audiobookshelf_url="https://abs.example.com",
    audiobookshelf_token="test-token",
    audiobookshelf_library_ids="lib_books",
    calibre_backend="content-server",
    calibre_url="https://calibre.example.com",
    shelfmark_url="https://shelfmark.example.com",
)


async def make_client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async for test_client in make_client(ALL_SOURCES):
        yield test_client


def mock_audiobookshelf(payload: dict | None = None) -> None:
    respx.get("https://abs.example.com/api/libraries/lib_books/search").mock(
        return_value=httpx.Response(200, json=payload or load_json("abs_search.json"))
    )


def mock_calibre() -> None:
    respx.get("https://calibre.example.com/ajax/search").mock(
        return_value=httpx.Response(200, json={"book_ids": [12]})
    )
    respx.get("https://calibre.example.com/ajax/books").mock(
        return_value=httpx.Response(200, json={"12": load_json("calibre_books.json")["12"]})
    )


async def test_healthz(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_index_renders_and_prefills_the_query(client: httpx.AsyncClient) -> None:
    response = await client.get("/", params={"q": "dune"})

    assert response.status_code == 200
    assert 'value="dune"' in response.text
    assert "Search in Shelfmark" in response.text


@respx.mock
async def test_search_returns_both_sources_separately(client: httpx.AsyncClient) -> None:
    mock_audiobookshelf()
    mock_calibre()

    response = await client.get("/api/search", params={"q": "wizards first rule"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "wizards first rule"

    sources = {source["key"]: source for source in payload["sources"]}
    assert list(sources) == ["audiobookshelf", "calibre"]
    assert sources["audiobookshelf"]["status"] == "ok"
    assert sources["audiobookshelf"]["count"] == 1
    assert sources["audiobookshelf"]["results"][0]["title"] == "Wizards First Rule"
    assert sources["calibre"]["status"] == "ok"
    assert sources["calibre"]["results"][0]["title"] == "Wizard's First Rule"


@respx.mock
async def test_one_failing_source_does_not_blank_the_other(client: httpx.AsyncClient) -> None:
    respx.get("https://abs.example.com/api/libraries/lib_books/search").mock(
        return_value=httpx.Response(500)
    )
    mock_calibre()

    response = await client.get("/api/search", params={"q": "dune"})

    assert response.status_code == 200, "a dead backend is data, not an API error"
    sources = {source["key"]: source for source in response.json()["sources"]}
    assert sources["audiobookshelf"]["status"] == "error"
    assert "HTTP 500" in sources["audiobookshelf"]["error"]
    assert sources["audiobookshelf"]["count"] == 0
    assert sources["calibre"]["status"] == "ok"
    assert sources["calibre"]["count"] == 1


@respx.mock
async def test_empty_result_set_is_reported_as_ok_with_zero(client: httpx.AsyncClient) -> None:
    mock_audiobookshelf({"book": []})
    respx.get("https://calibre.example.com/ajax/search").mock(
        return_value=httpx.Response(200, json={"book_ids": []})
    )

    response = await client.get("/api/search", params={"q": "nothing"})

    sources = {source["key"]: source for source in response.json()["sources"]}
    assert all(source["status"] == "ok" and source["count"] == 0 for source in sources.values())


async def test_unconfigured_sources_are_reported_as_disabled() -> None:
    async for client in make_client(Settings(shelfmark_url="https://shelfmark.example.com")):
        response = await client.get("/api/search", params={"q": "dune"})

        sources = {source["key"]: source for source in response.json()["sources"]}
        assert sources["audiobookshelf"]["status"] == "disabled"
        assert sources["calibre"]["status"] == "disabled"


@pytest.mark.parametrize("query", ["", "   "])
async def test_blank_query_is_rejected(client: httpx.AsyncClient, query: str) -> None:
    response = await client.get("/api/search", params={"q": query})

    assert response.status_code == 400


@respx.mock
async def test_shelfmark_url_is_built_and_encoded(client: httpx.AsyncClient) -> None:
    mock_audiobookshelf({"book": []})
    respx.get("https://calibre.example.com/ajax/search").mock(
        return_value=httpx.Response(200, json={"book_ids": []})
    )

    response = await client.get("/api/search", params={"q": "salt & fire"})

    assert response.json()["shelfmark_url"] == (
        "https://shelfmark.example.com/?q=salt+%26+fire&content_type=combined"
    )


@respx.mock
async def test_shelfmark_url_is_null_when_unconfigured() -> None:
    async for client in make_client(
        Settings(
            audiobookshelf_url="https://abs.example.com", audiobookshelf_library_ids="lib_books"
        )
    ):
        mock_audiobookshelf({"book": []})

        response = await client.get("/api/search", params={"q": "dune"})

        assert response.json()["shelfmark_url"] is None


@respx.mock
async def test_cover_proxy_streams_the_upstream_image(client: httpx.AsyncClient) -> None:
    route = respx.get("https://abs.example.com/api/items/li_1/cover").mock(
        return_value=httpx.Response(
            200, content=b"jpegbytes", headers={"content-type": "image/png"}
        )
    )

    response = await client.get("/api/cover/audiobookshelf/li_1")

    assert response.status_code == 200
    assert response.content == b"jpegbytes"
    assert response.headers["content-type"] == "image/png"
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"


@respx.mock
async def test_cover_proxy_reports_missing_covers_as_404(client: httpx.AsyncClient) -> None:
    respx.get("https://abs.example.com/api/items/nope/cover").mock(return_value=httpx.Response(404))

    response = await client.get("/api/cover/audiobookshelf/nope")

    assert response.status_code == 404


async def test_cover_proxy_rejects_unknown_sources(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/cover/nonsense/1")

    assert response.status_code == 404
