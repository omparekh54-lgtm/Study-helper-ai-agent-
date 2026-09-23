"""StudyForge API entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.db import init_db
from app.jobs import jobs
from app.routers import documents, system, topics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("studyforge")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    await init_db()
    await jobs.start()
    log.info(
        "StudyForge %s ready (llm=%s, gemini=%s, groq=%s, youtube=%s)",
        __version__, settings.llm_mode, bool(settings.gemini_api_key), bool(settings.groq_api_key), bool(settings.youtube_api_key),
    )
    yield
    await jobs.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.frontend_origin_regex or None,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Content-Range", "Accept-Ranges"],
        max_age=3600,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query"))
        message = "Please choose a file to upload." if field == "file" else f"Invalid request: {first.get('msg', 'bad input')}"
        return JSONResponse(status_code=422, content={"detail": message})

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"name": settings.app_name, "version": __version__, "docs": "/docs", "health": "/api/health"}

    app.include_router(system.router)
    app.include_router(documents.router)
    app.include_router(topics.router)
    return app


app = create_app()
