"""Text-to-speech with graceful degradation: edge-tts → gTTS → silent track.

A silent track still produces a usable video (slides + captions), so a TTS outage never
blocks the feature.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.services.video.assemble import probe_duration, run_ffmpeg

log = logging.getLogger(__name__)

WORDS_PER_SECOND = 2.6


def estimate_seconds(text: str) -> float:
    return max(2.5, len(text.split()) / WORDS_PER_SECOND)


async def _edge_tts(text: str, out: Path, voice: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await asyncio.wait_for(communicate.save(str(out)), timeout=60)


def _gtts(text: str, out: Path) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="en").save(str(out))


async def _silence(out: Path, seconds: float) -> None:
    await run_ffmpeg(
        ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{seconds:.2f}", "-c:a", "libmp3lame", "-q:a", "9", str(out)]
    )


async def synthesize(text: str, out: Path, voice: str, offline: bool = False) -> tuple[float, str]:
    """Write narration audio to `out`; return (duration_seconds, engine_used)."""
    engines: list[str] = [] if offline else ["edge-tts", "gtts"]
    for engine in engines:
        try:
            if engine == "edge-tts":
                await _edge_tts(text, out, voice)
            else:
                await asyncio.wait_for(asyncio.to_thread(_gtts, text, out), timeout=60)
            if out.exists() and out.stat().st_size > 1000:
                return await probe_duration(out), engine
        except Exception as exc:  # noqa: BLE001 — try the next engine
            log.warning("TTS engine %s failed: %s", engine, exc)
    seconds = estimate_seconds(text)
    await _silence(out, seconds)
    return seconds, "silent"
