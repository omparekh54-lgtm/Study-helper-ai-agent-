"""Health check (also used by Render and by the frontend to wake a sleeping instance)."""

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.services.sample import sample_pdf

from app import __version__
from app.api_models import HealthOut
from app.config import get_settings
from app.db import SessionLocal
from app.services.video.assemble import ffmpeg_available

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/sample.pdf", include_in_schema=False)
async def sample() -> Response:
    """Sample notes for the "Try a sample document" button."""
    return Response(sample_pdf(), media_type="application/pdf", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    s = get_settings()
    db_ok = True
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    if s.is_fake_llm:
        generator, verifier = "fake", "fake"
    else:
        generator = "gemini" if s.gemini_api_key else "missing"
        verifier = "groq" if s.groq_api_key else "none"
    return HealthOut(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        generator=generator,
        verifier=verifier,
        video=ffmpeg_available(),
        youtube="api" if s.youtube_api_key else "search",
        version=__version__,
    )
