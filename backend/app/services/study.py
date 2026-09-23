"""Outline extraction and per-topic study-kit generation."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.services.llm import JSONGenerator
from app.services.llm.prompts import KIT_SYSTEM, OUTLINE_SYSTEM, format_chunks, kit_prompt, outline_prompt
from app.services.llm.schemas import Beat, Outline, StudyKit

log = logging.getLogger(__name__)

MAX_TOPICS = 16
KIT_SOURCE_CHARS = 32_000


@dataclass
class ChunkRef:
    idx: int
    loc_start: int
    loc_end: int
    text: str
    loc: str  # "p. 4" / "pp. 4–5"


@dataclass
class PlannedTopic:
    unit_idx: int
    unit_title: str
    title: str
    summary: str
    key_points: list[str]
    chunk_idxs: list[int]


def _clean(s: str, limit: int) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


async def build_outline(generator: JSONGenerator, chunks: list[ChunkRef], char_count: int) -> tuple[str, str, list[PlannedTopic]]:
    material = format_chunks([(c.idx, c.loc, c.text) for c in chunks])
    outline = await generator.generate_json(
        system=OUTLINE_SYSTEM,
        prompt=outline_prompt(material, char_count),
        schema=Outline,
        max_output_tokens=16_384,
    )
    return normalize_outline(outline, chunks)


def normalize_outline(outline: Outline, chunks: list[ChunkRef]) -> tuple[str, str, list[PlannedTopic]]:
    """Validate chunk references, drop empty/duplicate topics, and assign orphan chunks."""
    valid = {c.idx for c in chunks}
    planned: list[PlannedTopic] = []
    seen_titles: set[str] = set()
    for u_i, unit in enumerate(outline.units):
        for t in unit.topics:
            ids = sorted({i for i in t.chunk_ids if i in valid})
            title = _clean(t.title, 90)
            key = title.lower()
            if not ids or not title or key in seen_titles:
                continue
            seen_titles.add(key)
            planned.append(
                PlannedTopic(
                    unit_idx=u_i,
                    unit_title=_clean(unit.title, 120) or f"Unit {u_i + 1}",
                    title=title,
                    summary=_clean(t.summary, 400),
                    key_points=[_clean(k, 160) for k in t.key_points if k.strip()][:6],
                    chunk_idxs=ids,
                )
            )

    if not planned:
        raise ValueError("The model returned an empty outline")

    # Any substantial chunk the outline forgot is attached to the nearest topic.
    covered = {i for t in planned for i in t.chunk_idxs}
    for c in chunks:
        if c.idx in covered or len(c.text) < 200:
            continue
        nearest = min(planned, key=lambda t: min(abs(c.idx - i) for i in t.chunk_idxs))
        nearest.chunk_idxs = sorted({*nearest.chunk_idxs, c.idx})

    # Keep document order: units by their first chunk, topics by their first chunk within a unit.
    unit_first: dict[int, int] = {}
    for t in planned:
        unit_first[t.unit_idx] = min(unit_first.get(t.unit_idx, 10**9), t.chunk_idxs[0])
    planned.sort(key=lambda t: (unit_first[t.unit_idx], t.unit_idx, t.chunk_idxs[0]))
    planned = planned[:MAX_TOPICS]

    # Re-number units densely in display order.
    remap: dict[int, int] = {}
    for t in planned:
        remap.setdefault(t.unit_idx, len(remap))
        t.unit_idx = remap[t.unit_idx]

    return _clean(outline.document_title, 150), _clean(outline.overview, 800), planned


async def build_kit(
    generator: JSONGenerator,
    *,
    topic_title: str,
    unit_title: str,
    doc_title: str,
    summary: str,
    chunks: list[ChunkRef],
) -> StudyKit:
    source = format_chunks([(c.idx, c.loc, c.text) for c in chunks], max_chars=KIT_SOURCE_CHARS)
    kit = await generator.generate_json(
        system=KIT_SYSTEM,
        prompt=kit_prompt(
            topic_title=topic_title, unit_title=unit_title, doc_title=doc_title, summary=summary, source=source
        ),
        schema=StudyKit,
        max_output_tokens=24_576,
    )
    kit.video = sanitize_beats(kit.video, topic_title)
    kit.youtube_query = _clean(kit.youtube_query, 120) or f"{topic_title} explained"
    return kit


def sanitize_beats(beats: list[Beat], topic_title: str) -> list[Beat]:
    cleaned: list[Beat] = []
    for b in beats[:9]:
        narration = _clean(b.narration, 600)
        if not narration:
            continue
        cleaned.append(
            b.model_copy(
                update={
                    "heading": _clean(b.heading, 70),
                    "points": [_clean(p, 110) for p in b.points if p.strip()][:4],
                    "quote": _clean(b.quote, 260),
                    "term": _clean(b.term, 60),
                    "definition": _clean(b.definition, 260),
                    "narration": narration,
                }
            )
        )
    if not cleaned or cleaned[0].kind != "title":
        cleaned.insert(
            0,
            Beat(kind="title", heading=topic_title, points=[], quote="", term="", definition="",
                 narration=f"Let's take a closer look at {topic_title}.", chunk_id=0),
        )
    return cleaned
