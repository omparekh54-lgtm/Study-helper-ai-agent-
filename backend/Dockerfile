# StudyForge API — runs on Render's free Docker web service (512 MB RAM, 0.1 CPU).
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg: video encoding · fonts-inter: slide typography · fonts-dejavu-core: PDF unicode coverage
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-inter fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# appuser owns /app so the SQLite fallback (used only when DATABASE_URL is unset) can create its file.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30"]
