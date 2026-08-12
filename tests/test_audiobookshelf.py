from __future__ import annotations

import httpx
import pytest
import respx

from app.clients.audiobookshelf import AudiobookshelfClient
from app.clients.base import SourceError
from app.config import Settings
from tests.conftest import load_json


@respx.mock
async def test_search_discovers_book_libraries_and_maps_results(
    http_client: httpx.AsyncClient, abs_settings: Settings
) -> None:
    libraries = respx.get("https://abs.example.com/api/libraries").mock(
        return_value=httpx.Response(200, json=load_json("abs_libraries.json"))
    )
    search_books = respx.get("https://abs.example.com/api/libraries/lib_books/search").mock(
        return_value=httpx.Response(200, json=load_json("abs_search.json"))
    )
    search_kids = respx.get("https://abs.example.com/api/libraries/lib_books_2/search").mock(
        return_value=httpx.Response(200, json={"book": [], "series": []})
    )
    podcasts = respx.get("https://abs.example.com/api/libraries/lib_pods/search")

    results = await AudiobookshelfClient(http_client, abs_settings).search("wizards", 25)

    assert libraries.called
    assert search_books.called and search_kids.called
    assert not podcasts.called, "podcast libraries are skipped by default"

    assert len(results) == 1
    book = results[0]
    assert book.title == "Wizards First Rule"
    assert book.authors == ["Terry Goodkind"]
    assert book.series == "Sword of Truth"
    assert book.series_index == "1"
    assert book.year == "2008"
    assert book.narrators == ["Sam Tsoutsouvas"]
    assert book.formats == ["MP3"]
    assert book.identifiers == {"asin": "B002V0QK4C"}
    assert book.item_url == "https://abs.example.com/item/li_8gch9ve09orgn4fdz8"
    assert book.cover_url == "/api/cover/audiobookshelf/li_8gch9ve09orgn4fdz8"


@respx.mock
async def test_search_sends_bearer_token_and_limit(
    http_client: httpx.AsyncClient, abs_settings: Settings
) -> None:
    respx.get("https://abs.example.com/api/libraries").mock(
        return_value=httpx.Response(200, json={"libraries": [{"id": "lib_books"}]})
    )
    route = respx.get("https://abs.example.com/api/libraries/lib_books/search").mock(
        return_value=httpx.Response(200, json={"book": []})
    )

    await AudiobookshelfClient(http_client, abs_settings).search("dune", 7)

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.url.params["q"] == "dune"
    assert request.url.params["limit"] == "7"


@respx.mock
async def test_configured_library_ids_skip_discovery(http_client: httpx.AsyncClient) -> None:
    settings = Settings(
        audiobookshelf_url="https://abs.example.com",
        audiobookshelf_token="t",
        audiobookshelf_library_ids="lib_only",
    )
    libraries = respx.get("https://abs.example.com/api/libraries")
    route = respx.get("https://abs.example.com/api/libraries/lib_only/search").mock(
        return_value=httpx.Response(200, json={"book": []})
    )

    await AudiobookshelfClient(http_client, settings).search("dune", 25)

    assert not libraries.called
    assert route.called


@respx.mock
async def test_podcast_libraries_included_when_enabled(http_client: httpx.AsyncClient) -> None:
    settings = Settings(
        audiobookshelf_url="https://abs.example.com",
        audiobookshelf_token="t",
        audiobookshelf_include_podcasts=True,
    )
    respx.get("https://abs.example.com/api/libraries").mock(
        return_value=httpx.Response(200, json=load_json("abs_libraries.json"))
    )
    respx.get("https://abs.example.com/api/libraries/lib_books/search").mock(
        return_value=httpx.Response(200, json={"book": []})
    )
    respx.get("https://abs.example.com/api/libraries/lib_books_2/search").mock(
        return_value=httpx.Response(200, json={"book": []})
    )
    podcasts = respx.get("https://abs.example.com/api/libraries/lib_pods/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "podcast": [
                    {
                        "libraryItem": {
                            "id": "li_pod",
                            "mediaType": "podcast",
                            "media": {"metadata": {"title": "A Podcast"}},
                        }
                    }
                ]
            },
        )
    )

    results = await AudiobookshelfClient(http_client, settings).search("a", 25)

    assert podcasts.called
    assert [book.title for book in results] == ["A Podcast"]


@respx.mock
async def test_library_discovery_is_cached_across_searches(
    http_client: httpx.AsyncClient, abs_settings: Settings
) -> None:
    libraries = respx.get("https://abs.example.com/api/libraries").mock(
        return_value=httpx.Response(200, json={"libraries": [{"id": "lib_books"}]})
    )
    respx.get("https://abs.example.com/api/libraries/lib_books/search").mock(
        return_value=httpx.Response(200, json={"book": []})
    )

    client = AudiobookshelfClient(http_client, abs_settings)
    await client.search("one", 25)
    await client.search("two", 25)

    assert libraries.call_count == 1


@respx.mock
async def test_duplicate_items_across_libraries_are_deduped(
    http_client: httpx.AsyncClient, abs_settings: Settings
) -> None:
    payload = load_json("abs_search.json")
    respx.get("https://abs.example.com/api/libraries").mock(
        return_value=httpx.Response(
            200, json={"libraries": [{"id": "lib_books"}, {"id": "lib_books_2"}]}
        )
    )
    respx.get("https://abs.example.com/api/libraries/lib_books/search").mock(
        return_value=httpx.Response(200, json=payload)
    )
    respx.get("https://abs.example.com/api/libraries/lib_books_2/search").mock(
        return_value=httpx.Response(200, json=payload)
    )

    results = await AudiobookshelfClient(http_client, abs_settings).search("wizards", 25)

    assert len(results) == 1


@respx.mock
async def test_results_are_capped_at_the_limit(
    http_client: httpx.AsyncClient, abs_settings: Settings
) -> None:
    respx.get("https://abs.example.com/api/libraries").mock(
        return_value=httpx.Response(200, json={"libraries": [{"id": "lib_books"}]})
    )
    respx.get("https://abs.example.com/api/libraries/lib_books/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "book": [
                    {"libraryItem": {"id": f"li_{n}", "media": {"metadata": {"title": f"B{n}"}}}}
                    for n in range(10)
                ]
            },
        )
    )

    results = await AudiobookshelfClient(http_client, abs_settings).search("b", 3)

    assert len(results) == 3


@respx.mock
async def test_http_error_becomes_source_error(
    http_client: httpx.AsyncClient, abs_settings: Settings
) -> None:
    respx.get("https://abs.example.com/api/libraries").mock(return_value=httpx.Response(401))

    with pytest.raises(SourceError, match="HTTP 401"):
        await AudiobookshelfClient(http_client, abs_settings).search("dune", 25)


@respx.mock
async def test_connection_error_becomes_source_error(
    http_client: httpx.AsyncClient, abs_settings: Settings
) -> None:
    respx.get("https://abs.example.com/api/libraries").mock(
        side_effect=httpx.ConnectError("nope", request=httpx.Request("GET", "https://x"))
    )

    with pytest.raises(SourceError):
        await AudiobookshelfClient(http_client, abs_settings).search("dune", 25)


@respx.mock
async def test_cover_is_fetched_with_the_token(
    http_client: httpx.AsyncClient, abs_settings: Settings
) -> None:
    route = respx.get("https://abs.example.com/api/items/li_1/cover").mock(
        return_value=httpx.Response(
            200, content=b"jpegbytes", headers={"content-type": "image/jpeg"}
        )
    )

    response = await AudiobookshelfClient(http_client, abs_settings).cover("li_1")

    assert response.content == b"jpegbytes"
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"
