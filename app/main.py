"""FastAPI application: one page, one search endpoint, one cover proxy."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.clients.base import SourceError
from app.config import Settings
from app.models import SearchResponse
from app.search import build_clients, search_all

BASE_DIR = Path(__file__).parent

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Tests pass their own settings instead of using the env."""
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level.upper())
    templates = Jinja2Templates(directory=BASE_DIR / "templates")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Own a single shared HTTP client for the app's lifetime."""
        async with httpx.AsyncClient(
            timeout=settings.request_timeout,
            verify=settings.verify_tls,
            follow_redirects=True,
        ) as http_client:
            app.state.http_client = http_client
            app.state.clients = build_clients(http_client, settings)
            logger.info("Configured sources: %s", ", ".join(app.state.clients) or "none")
            yield

    app = FastAPI(title="search-books", lifespan=lifespan)
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, q: str = "") -> HTMLResponse:
        """The search page. ``?q=`` prefills the box so result pages are linkable."""
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "query": q,
                "shelfmark_configured": bool(settings.shelfmark_url),
                "sources_configured": bool(request.app.state.clients),
            },
        )

    @app.get("/api/search")
    async def api_search(request: Request, q: str = Query(default="")) -> SearchResponse:
        query = q.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

        return await search_all(query, request.app.state.clients, settings)

    @app.get("/api/cover/{source}/{item_id}")
    async def api_cover(request: Request, source: str, item_id: str) -> Response:
        """Proxy cover images so backend credentials never reach the browser."""
        client = request.app.state.clients.get(source)
        if client is None:
            raise HTTPException(status_code=404, detail=f"Unknown source '{source}'")

        try:
            upstream = await client.cover(item_id)
        except (SourceError, httpx.HTTPError) as exc:
            logger.info("Cover fetch failed for %s/%s: %s", source, item_id, exc)
            raise HTTPException(status_code=404, detail="Cover not available") from exc

        return Response(
            content=upstream.content,
            media_type=upstream.headers.get("content-type", "image/jpeg"),
            # "private": these are covers from a private library, so only the browser
            # that asked for them should cache them -- never a shared proxy.
            headers={"Cache-Control": "private, max-age=86400"},
        )

    return app


app = create_app()
