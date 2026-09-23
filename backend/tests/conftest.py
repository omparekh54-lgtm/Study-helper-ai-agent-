import os
import tempfile

# Configure the app for offline testing *before* anything imports it.
_TMP = tempfile.mkdtemp(prefix="studyforge-test-")
os.environ.update(
    {
        "LLM_MODE": "fake",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP}/test.db",
        "AUTO_GENERATE_VIDEOS": "true",
        "UPLOADS_PER_IP_PER_HOUR": "1000",
        "YOUTUBE_API_KEY": "",
        "GEMINI_API_KEY": "",
        "GROQ_API_KEY": "",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(scope="session")
def sample_pdf() -> bytes:
    from app.services.sample import sample_pdf as build

    return build()


@pytest.fixture(scope="session")
async def client():
    from app.db import init_db
    from app.jobs import jobs
    from app.main import app

    await init_db()
    await jobs.start()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await jobs.stop()
