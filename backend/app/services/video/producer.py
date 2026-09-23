"""Turn a topic's beat script into a narrated MP4 (+ timeline for captions and transcript)."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.video.assemble import concat_segments, make_segment, probe_duration
from app.services.video.slides import SlideContext, SlideRenderer
from app.services.video.tts import synthesize

log = logging.getLogger(__name__)

PAUSE_AFTER_BEAT = 0.6  # seconds of breathing room between scenes

ProgressFn = Callable[[str], Awaitable[None]]


@dataclass
class VideoResult:
    mp4: bytes
    duration: float
    timeline: list[dict]
    tts_engine: str
    poster: bytes = b""


async def produce_video(
    beats: list[dict],
    *,
    topic_title: str,
    unit_title: str,
    doc_title: str,
    source_for_chunk: Callable[[int], str],
    voice: str,
    offline: bool,
    progress: ProgressFn,
    width: int = 1280,
    height: int = 720,
) -> VideoResult:
    renderer = SlideRenderer(width, height)
    total = len(beats)
    engines: set[str] = set()
    poster = b""

    with tempfile.TemporaryDirectory(prefix="sf-video-") as tmp_dir:
        tmp = Path(tmp_dir)
        segments: list[Path] = []
        timeline: list[dict] = []
        clock = 0.0

        for i, beat in enumerate(beats):
            await progress(f"Narrating scene {i + 1} of {total}")
            audio = tmp / f"a{i:02d}.mp3"
            speech, engine = await synthesize(beat["narration"], audio, voice, offline=offline)
            engines.add(engine)

            await progress(f"Designing scene {i + 1} of {total}")
            ctx = SlideContext(
                index=i,
                total=total,
                topic_title=topic_title,
                unit_title=unit_title,
                doc_title=doc_title,
                source=source_for_chunk(int(beat.get("chunk_id") or 0)),
            )
            image = tmp / f"s{i:02d}.png"
            slide = await asyncio.to_thread(renderer.render, beat, ctx)
            await asyncio.to_thread(slide.save, image, "PNG")
            if i == 0:
                buf = io.BytesIO()
                await asyncio.to_thread(slide.save, buf, "JPEG", quality=85, optimize=True)
                poster = buf.getvalue()

            await progress(f"Encoding scene {i + 1} of {total}")
            seconds = speech + PAUSE_AFTER_BEAT
            segment = tmp / f"seg{i:02d}.mp4"
            await make_segment(image, audio, seconds, segment)
            segments.append(segment)
            timeline.append(
                {"start": round(clock, 2), "end": round(clock + speech, 2), "heading": beat.get("heading", ""), "narration": beat["narration"]}
            )
            clock += seconds

        await progress("Putting it all together")
        out = tmp / "video.mp4"
        await concat_segments(segments, out)
        duration = await probe_duration(out)
        data = out.read_bytes()

    engine = "silent" if engines == {"silent"} else next((e for e in ("edge-tts", "gtts") if e in engines), "silent")
    log.info("Rendered %d-scene video: %.1fs, %d KB, tts=%s", total, duration, len(data) // 1024, engine)
    return VideoResult(mp4=data, duration=duration, timeline=timeline, tts_engine=engine, poster=poster)


# ---- Captions -----------------------------------------------------------------------------------

_SENTENCES = re.compile(r"(?<=[.!?])\s+")


def _ts(seconds: float) -> str:
    h, rem = divmod(max(seconds, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def build_vtt(timeline: list[dict]) -> str:
    """WebVTT captions: each scene's narration split into sentences, timed by length."""
    lines = ["WEBVTT", ""]
    n = 1
    for scene in timeline:
        sentences = [s for s in _SENTENCES.split(scene.get("narration", "").strip()) if s]
        if not sentences:
            continue
        span = max(scene["end"] - scene["start"], 0.5)
        total_chars = sum(len(s) for s in sentences)
        t = scene["start"]
        for sentence in sentences:
            dur = span * len(sentence) / total_chars
            lines += [str(n), f"{_ts(t)} --> {_ts(t + dur)}", sentence, ""]
            n += 1
            t += dur
    return "\n".join(lines)
