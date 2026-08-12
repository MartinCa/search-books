"""Environment-driven configuration.

Everything the app needs is passed as environment variables so the container stays
stateless. A source whose URL is unset is reported as ``disabled`` rather than failing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator, Field, HttpUrl, TypeAdapter, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class CalibreBackend(StrEnum):
    """Which Calibre-side service to query."""

    AUTO = "auto"
    CONTENT_SERVER = "content-server"
    CALIBRE_WEB = "calibre-web"
    NONE = "none"


class ShelfmarkContentType(StrEnum):
    """Search mode preselected in Shelfmark's UI."""

    COMBINED = "combined"
    EBOOK = "ebook"
    AUDIOBOOK = "audiobook"


def _split_csv(value: object) -> object:
    """Accept ``a,b,c`` for list-typed settings, since env vars are flat strings."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


# NoDecode is essential: without it pydantic-settings JSON-decodes env values for
# list-typed fields before validation runs, so a plain "a,b" raises SettingsError and the
# validator below never sees it.
CsvList = Annotated[list[str], NoDecode, BeforeValidator(_split_csv)]

_URL_ADAPTER = TypeAdapter(HttpUrl)


class Settings(BaseSettings):
    """Application settings, read once at startup."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Audiobookshelf
    audiobookshelf_url: str | None = None
    audiobookshelf_token: str | None = None
    audiobookshelf_library_ids: CsvList = Field(default_factory=list)
    audiobookshelf_include_podcasts: bool = False

    # Calibre / Calibre-Web
    calibre_backend: CalibreBackend = CalibreBackend.AUTO
    calibre_url: str | None = None
    calibre_username: str | None = None
    calibre_password: str | None = None
    calibre_library_id: str | None = None

    # Shelfmark
    shelfmark_url: str | None = None
    shelfmark_content_type: ShelfmarkContentType = ShelfmarkContentType.COMBINED

    # Server. HOST and PORT are deliberately absent: they are read by the container's
    # entrypoint when it launches uvicorn, not by the application itself.
    search_limit: int = Field(default=25, ge=1, le=200)
    request_timeout: float = Field(default=10.0, gt=0)
    verify_tls: bool = True
    log_level: str = "INFO"

    @field_validator("audiobookshelf_url", "calibre_url", "shelfmark_url", mode="after")
    @classmethod
    def _normalize_url(cls, value: str | None) -> str | None:
        """Validate the URL and drop the trailing slash so paths can be appended blindly."""
        if value is None:
            return None
        value = value.strip().rstrip("/")
        if not value:
            return None
        _URL_ADAPTER.validate_python(value)
        return value

    @property
    def audiobookshelf_enabled(self) -> bool:
        return bool(self.audiobookshelf_url)

    @property
    def resolved_calibre_backend(self) -> CalibreBackend:
        """Resolve ``auto`` into a concrete backend based on whether a URL is configured."""
        if not self.calibre_url:
            return CalibreBackend.NONE
        if self.calibre_backend is CalibreBackend.AUTO:
            return CalibreBackend.CONTENT_SERVER
        return self.calibre_backend

    @property
    def calibre_enabled(self) -> bool:
        return self.resolved_calibre_backend is not CalibreBackend.NONE

    @property
    def calibre_auth(self) -> tuple[str, str] | None:
        """HTTP Basic credentials, when both halves are configured."""
        if self.calibre_username and self.calibre_password:
            return (self.calibre_username, self.calibre_password)
        return None
