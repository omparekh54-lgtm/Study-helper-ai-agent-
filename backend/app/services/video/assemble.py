"""ffmpeg helpers: probe durations, render still-image segments, and concatenate them.

Encoding slides as still images at a low frame rate with x264's `stillimage` tune keeps
CPU cost tiny — important on a 0.1-CPU free instance.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

FPS = 5


class FFmpegError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


async def _run(binary: str, args: list[str], timeout: float = 600) -> str:
    proc = await asyncio.create_subprocess_exec(
        binary, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise FFmpegError(f"{binary} timed out") from None
    if proc.returncode != 0:
        tail = err.decode(errors="replace").strip().splitlines()[-5:]
        raise FFmpegError(f"{binary} failed: {' | '.join(tail)}")
    return out.decode(errors="replace")


async def run_ffmpeg(args: list[str], timeout: float = 600) -> None:
    await _run("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", *args], timeout)


async def probe_duration(path: Path) -> float:
    out = await _run("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], 60)
    return float(out.strip() or 0)


async def make_segment(image: Path, audio: Path, seconds: float, out: Path) -> None:
    await run_ffmpeg(
        [
            "-loop", "1", "-framerate", str(FPS), "-i", str(image),
            "-i", str(audio),
            "-af", "apad",
            "-t", f"{seconds:.2f}",
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "24",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "1",
            str(out),
        ]
    )


async def concat_segments(segments: list[Path], out: Path) -> None:
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in segments))
    await run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(out)])
