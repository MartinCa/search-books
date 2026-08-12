from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


_ENV_PREFIXES = ("AUDIOBOOKSHELF_", "CALIBRE_", "SHELFMARK_", "SEARCH_", "REQUEST_", "VERIFY_")


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the host environment from leaking into Settings under test."""
    import os

    for name in list(os.environ):
        if name.startswith(_ENV_PREFIXES):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        yield client


@pytest.fixture
def abs_settings() -> Settings:
    return Settings(
        audiobookshelf_url="https://abs.example.com",
        audiobookshelf_token="test-token",
        calibre_url=None,
        shelfmark_url=None,
    )


@pytest.fixture
def calibre_settings() -> Settings:
    return Settings(
        audiobookshelf_url=None,
        calibre_backend="content-server",
        calibre_url="https://calibre.example.com",
        shelfmark_url=None,
    )


@pytest.fixture
def calibre_web_settings() -> Settings:
    return Settings(
        audiobookshelf_url=None,
        calibre_backend="calibre-web",
        calibre_url="https://cw.example.com",
        shelfmark_url=None,
    )
