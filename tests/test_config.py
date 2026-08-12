from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import CalibreBackend, Settings, ShelfmarkContentType


def test_urls_lose_their_trailing_slash() -> None:
    settings = Settings(
        audiobookshelf_url="https://abs.example.com/",
        calibre_url="https://calibre.example.com///",
        shelfmark_url="https://shelfmark.example.com/",
    )

    assert settings.audiobookshelf_url == "https://abs.example.com"
    assert settings.calibre_url == "https://calibre.example.com"
    assert settings.shelfmark_url == "https://shelfmark.example.com"


def test_blank_url_is_treated_as_unset() -> None:
    settings = Settings(audiobookshelf_url="   ")

    assert settings.audiobookshelf_url is None
    assert settings.audiobookshelf_enabled is False


def test_invalid_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(calibre_url="not-a-url")


def test_library_ids_parse_from_csv() -> None:
    settings = Settings(audiobookshelf_library_ids="lib_a, lib_b ,, lib_c")

    assert settings.audiobookshelf_library_ids == ["lib_a", "lib_b", "lib_c"]


@pytest.mark.parametrize(
    ("backend", "url", "expected"),
    [
        ("auto", "https://calibre.example.com", CalibreBackend.CONTENT_SERVER),
        ("auto", None, CalibreBackend.NONE),
        ("calibre-web", "https://cw.example.com", CalibreBackend.CALIBRE_WEB),
        ("content-server", None, CalibreBackend.NONE),
        ("none", "https://calibre.example.com", CalibreBackend.NONE),
    ],
)
def test_calibre_backend_resolution(
    backend: str, url: str | None, expected: CalibreBackend
) -> None:
    settings = Settings(calibre_backend=backend, calibre_url=url)

    assert settings.resolved_calibre_backend is expected
    assert settings.calibre_enabled is (expected is not CalibreBackend.NONE)


def test_calibre_auth_requires_both_halves() -> None:
    assert Settings(calibre_username="u").calibre_auth is None
    assert Settings(calibre_password="p").calibre_auth is None
    assert Settings(calibre_username="u", calibre_password="p").calibre_auth == ("u", "p")


def test_defaults() -> None:
    settings = Settings()

    assert settings.search_limit == 25
    assert settings.request_timeout == 10.0
    assert settings.verify_tls is True
    assert settings.shelfmark_content_type is ShelfmarkContentType.COMBINED
    assert settings.audiobookshelf_include_podcasts is False


# Everything below loads settings the way the container does -- through the environment,
# not the constructor. Constructor-only tests bypass pydantic-settings' env source, which
# is where env-specific parsing (and its failure modes) actually live.


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("lib_a,lib_b", ["lib_a", "lib_b"]),
        ("lib_a, lib_b ,, lib_c", ["lib_a", "lib_b", "lib_c"]),
        ("lib_only", ["lib_only"]),
        ("", []),
        ("   ", []),
    ],
)
def test_library_ids_load_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]
) -> None:
    monkeypatch.setenv("AUDIOBOOKSHELF_LIBRARY_IDS", raw)

    assert Settings().audiobookshelf_library_ids == expected


def test_full_configuration_loads_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIOBOOKSHELF_URL", "https://abs.example.com/")
    monkeypatch.setenv("AUDIOBOOKSHELF_TOKEN", "token")
    monkeypatch.setenv("AUDIOBOOKSHELF_LIBRARY_IDS", "lib_a,lib_b")
    monkeypatch.setenv("AUDIOBOOKSHELF_INCLUDE_PODCASTS", "true")
    monkeypatch.setenv("CALIBRE_BACKEND", "calibre-web")
    monkeypatch.setenv("CALIBRE_URL", "https://cw.example.com")
    monkeypatch.setenv("SHELFMARK_URL", "https://shelfmark.example.com")
    monkeypatch.setenv("SHELFMARK_CONTENT_TYPE", "ebook")
    monkeypatch.setenv("SEARCH_LIMIT", "50")
    monkeypatch.setenv("VERIFY_TLS", "false")

    settings = Settings()

    assert settings.audiobookshelf_url == "https://abs.example.com"
    assert settings.audiobookshelf_library_ids == ["lib_a", "lib_b"]
    assert settings.audiobookshelf_include_podcasts is True
    assert settings.resolved_calibre_backend is CalibreBackend.CALIBRE_WEB
    assert settings.shelfmark_content_type is ShelfmarkContentType.EBOOK
    assert settings.search_limit == 50
    assert settings.verify_tls is False


def test_host_and_port_are_not_application_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """They belong to the container entrypoint; the app must ignore them, not choke."""
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")

    settings = Settings()

    assert not hasattr(settings, "port")
