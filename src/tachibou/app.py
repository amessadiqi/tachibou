"""FastAPI application."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from tachibou import APP_NAME, __version__
from tachibou.config import get_settings
from tachibou.database import create_db_engine, create_session_factory
from tachibou.migrate import upgrade_database


class SinglePageApplication(StaticFiles):
    """Serve the built interface and fall back to index.html for client routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or _looks_like_file(path):
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and not _looks_like_file(path):
            return await super().get_response("index.html", scope)
        return response


class HealthResponse(BaseModel):
    status: Literal["ok"]
    name: str
    version: str
    database: Literal["ok"]


def bundled_frontend_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    upgrade_database(settings)
    engine = create_db_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        engine.dispose()


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health(db: DbSession) -> HealthResponse:
    db.execute(text("SELECT 1 FROM app_metadata LIMIT 1"))
    return HealthResponse(status="ok", name=APP_NAME, version=__version__, database="ok")


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.include_router(router)
    frontend = bundled_frontend_dir()
    if (frontend / "index.html").is_file():
        app.mount("/", SinglePageApplication(directory=frontend, html=True), name="frontend")
    else:

        @app.get("/")
        def frontend_missing() -> PlainTextResponse:
            return PlainTextResponse(
                f"{APP_NAME} frontend assets are not installed.\n"
                "During development, start the Vite server in the frontend directory.\n"
                "A packaged release serves the interface from the backend.\n"
            )

    return app


def _looks_like_file(path: str) -> bool:
    return "." in Path(path).name
