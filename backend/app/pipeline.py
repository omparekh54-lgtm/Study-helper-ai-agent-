"""Document → outline → per-topic study kits → (background) narrated videos.

Every step persists its result before the next begins, so the pipeline is idempotent:
if the free-tier instance restarts or spins down mid-job, `JobManager.recover()` simply
re-runs it and completed work is skipped.
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Chunk, Document, QAItem, Question, Topic, VideoAsset
from app.services.llm import LLMError, LLMNotConfigured, get_generator, get_verifier
from app.services.parsing import loc_label
from app.services.study import ChunkRef, build_kit, build_outline
from app.services.verify import SourceChunk, verify_kit
from app.services.video.assemble import ffmpeg_available
from app.services.video.producer import produce_video
from app.services.youtube import find_videos

log = logging.getLogger(__name__)

MIN_MCQS = 4
TOPIC_CONCURRENCY = 2


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, LLMNotConfigured):
        return "The AI service isn't configured on the server yet (missing API key)."
    if isinstance(exc, LLMError):
        text = str(exc).lower()
        if "api key" in text:
            return "The AI service rejected the server's API key. Please check the configuration."
        return "The AI service is busy or out of free quota right now. Please try again in a few minutes."
    return "Something went wrong while generating this. Please try again."


async def _load_chunks(document_id: str, source_label: str) -> dict[int, ChunkRef]:
    async with SessionLocal() as s:
        rows = (await s.scalars(select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.idx))).all()
    return {
        c.idx: ChunkRef(c.idx, c.loc_start, c.loc_end, c.text, loc_label(source_label, c.loc_start, c.loc_end))
        for c in rows
    }


async def _set_doc(document_id: str, **fields) -> None:
    async with SessionLocal() as s:
        doc = await s.get(Document, document_id)
        if doc is None:
            return
        for k, v in fields.items():
            setattr(doc, k, v)
        await s.commit()


async def process_document(document_id: str, enqueue_video=None) -> None:
    async with SessionLocal() as s:
        doc = await s.get(Document, document_id)
        if doc is None or doc.status == "ready":
            return
        doc.status, doc.error = "processing", None
        source_label, char_count, doc_title = doc.source_label, doc.char_count, doc.title
        topic_count = await s.scalar(select(func.count()).select_from(Topic).where(Topic.document_id == document_id))
        await s.commit()

    chunks = await _load_chunks(document_id, source_label)
    started = time.monotonic()
    try:
        generator = get_generator()

        if not topic_count:
            await _set_doc(document_id, stage="outlining", stage_detail="Reading your document and mapping units and topics")
            title, overview, planned = await build_outline(generator, list(chunks.values()), char_count)
            async with SessionLocal() as s:
                doc = await s.get(Document, document_id)
                if title:
                    doc.title = title
                doc.summary = overview
                doc_title = doc.title
                for i, p in enumerate(planned):
                    locs = [chunks[c] for c in p.chunk_idxs]
                    s.add(
                        Topic(
                            document_id=document_id, idx=i, unit_idx=p.unit_idx, unit_title=p.unit_title,
                            title=p.title, summary=p.summary, key_points=p.key_points, chunk_idxs=p.chunk_idxs,
                            loc_label=loc_label(source_label, min(c.loc_start for c in locs), max(c.loc_end for c in locs)),
                        )
                    )
                await s.commit()
            log.info("Outlined %s into %d topics in %.1fs", document_id, len(planned), time.monotonic() - started)

        async with SessionLocal() as s:
            pending = (
                await s.scalars(
                    select(Topic.id).where(Topic.document_id == document_id, Topic.kit_status != "ready").order_by(Topic.idx)
                )
            ).all()
            total = await s.scalar(select(func.count()).select_from(Topic).where(Topic.document_id == document_id))

        progress = {"done": total - len(pending)}

        async def refresh_progress() -> None:
            await _set_doc(
                document_id, stage="building",
                stage_detail=f"Writing and fact-checking study kits · {progress['done']} of {total} topics ready",
            )

        await refresh_progress()
        sem = asyncio.Semaphore(TOPIC_CONCURRENCY)

        async def run(topic_id: str) -> None:
            async with sem:
                await build_topic(topic_id, chunks, doc_title, enqueue_video)
                progress["done"] += 1
                await refresh_progress()

        await asyncio.gather(*(run(tid) for tid in pending))

        async with SessionLocal() as s:
            doc = await s.get(Document, document_id)
            ready = await s.scalar(
                select(func.count()).select_from(Topic).where(Topic.document_id == document_id, Topic.kit_status == "ready")
            )
            if ready:
                doc.status, doc.stage, doc.stage_detail = "ready", "done", "Ready"
            else:
                last_error = await s.scalar(
                    select(Topic.kit_error).where(Topic.document_id == document_id, Topic.kit_error.is_not(None)).limit(1)
                )
                doc.status, doc.stage = "failed", "done"
                doc.error = last_error or "We couldn't generate study material for this document."
            await s.commit()
        log.info("Document %s finished in %.1fs (%d/%d topics ready)", document_id, time.monotonic() - started, ready, total)

    except Exception as exc:  # noqa: BLE001
        log.exception("Processing failed for %s", document_id)
        await _set_doc(document_id, status="failed", stage="done", error=friendly_error(exc))


async def build_topic(topic_id: str, chunks: dict[int, ChunkRef], doc_title: str, enqueue_video=None) -> None:
    settings = get_settings()
    async with SessionLocal() as s:
        topic = await s.get(Topic, topic_id)
        if topic is None:
            return
        topic.kit_status, topic.kit_error = "generating", None
        title, unit, summary, chunk_idxs = topic.title, topic.unit_title, topic.summary, list(topic.chunk_idxs)
        await s.commit()

    try:
        refs = [chunks[i] for i in chunk_idxs if i in chunks]
        sources = {c.idx: SourceChunk(c.idx, c.text, c.loc) for c in refs}
        generator = get_generator()

        mcqs, qas, kit = [], [], None
        for attempt in range(2):  # regenerate once if too little survives the fact-check
            kit = await build_kit(generator, topic_title=title, unit_title=unit, doc_title=doc_title, summary=summary, chunks=refs)
            mcqs, qas = await verify_kit(kit.mcqs, kit.qa, sources, get_verifier())
            if len(mcqs) >= MIN_MCQS:
                break
            log.warning("Topic %s: only %d MCQs survived verification (attempt %d)", topic_id, len(mcqs), attempt + 1)
        if not mcqs and not qas:
            raise ValueError("No questions survived fact-checking")

        youtube = await find_videos(kit.youtube_query, settings.youtube_api_key)

        async with SessionLocal() as s:
            topic = await s.get(Topic, topic_id)
            await s.execute(delete(Question).where(Question.topic_id == topic_id))
            await s.execute(delete(QAItem).where(QAItem.topic_id == topic_id))
            for i, c in enumerate(mcqs):
                m = c.item
                s.add(
                    Question(
                        topic_id=topic_id, idx=i, question=m.question, options=m.options, answer_index=m.answer_index,
                        explanation=m.explanation, difficulty=m.difficulty, source_quote=m.source_quote,
                        source_loc=c.chunk.loc, verification=c.verification,
                    )
                )
            for i, c in enumerate(qas):
                q = c.item
                s.add(
                    QAItem(
                        topic_id=topic_id, idx=i, question=q.question, answer=q.answer, kind=q.kind,
                        source_quote=q.source_quote, source_loc=c.chunk.loc, verification=c.verification,
                    )
                )
            topic.video_script = [b.model_dump() for b in kit.video]
            topic.youtube_query = kit.youtube_query
            topic.youtube = youtube
            topic.kit_status = "ready"
            queue_video = settings.auto_generate_videos and topic.video_status in ("none", "failed")
            if queue_video:
                topic.video_status, topic.video_detail, topic.video_error = "queued", "Waiting in line", None
            await s.commit()
        if queue_video and enqueue_video:
            enqueue_video(topic_id, priority=10)
        log.info("Topic %s ready: %d MCQs, %d Q&A", topic_id, len(mcqs), len(qas))

    except Exception as exc:  # noqa: BLE001
        log.exception("Study kit failed for topic %s", topic_id)
        async with SessionLocal() as s:
            topic = await s.get(Topic, topic_id)
            if topic is not None:
                topic.kit_status, topic.kit_error = "failed", friendly_error(exc)
                await s.commit()


async def generate_video(topic_id: str) -> None:
    settings = get_settings()
    async with SessionLocal() as s:
        topic = await s.get(Topic, topic_id)
        if topic is None or topic.kit_status != "ready" or not topic.video_script:
            return
        has_asset = await s.scalar(select(func.count()).select_from(VideoAsset).where(VideoAsset.topic_id == topic_id))
        if topic.video_status == "ready" and has_asset:
            return
        doc = await s.get(Document, topic.document_id)
        topic.video_status, topic.video_detail, topic.video_error = "generating", "Starting", None
        beats = [dict(b) for b in topic.video_script]
        title, unit, doc_title, source_label = topic.title, topic.unit_title, doc.title, doc.source_label
        document_id = topic.document_id
        await s.commit()

    try:
        if not ffmpeg_available():
            raise RuntimeError("ffmpeg is not installed on the server")
        chunks = await _load_chunks(document_id, source_label)

        async def progress(message: str) -> None:
            async with SessionLocal() as s2:
                t = await s2.get(Topic, topic_id)
                if t is not None:
                    t.video_detail = message
                    await s2.commit()

        result = await produce_video(
            beats,
            topic_title=title,
            unit_title=unit,
            doc_title=doc_title,
            source_for_chunk=lambda cid: chunks[cid].loc if cid in chunks else "",
            voice=settings.tts_voice,
            offline=settings.is_fake_llm,
            progress=progress,
            width=settings.video_width,
            height=settings.video_height,
        )

        async with SessionLocal() as s:
            topic = await s.get(Topic, topic_id)
            await s.execute(delete(VideoAsset).where(VideoAsset.topic_id == topic_id))
            s.add(
                VideoAsset(
                    topic_id=topic_id, mp4=result.mp4, poster=result.poster or None,
                    duration_s=result.duration, size_bytes=len(result.mp4),
                )
            )
            topic.video_script = [{**beat, **timing} for beat, timing in zip(beats, result.timeline)]
            topic.video_status, topic.video_detail = "ready", result.tts_engine
            await s.commit()

    except Exception as exc:  # noqa: BLE001
        log.exception("Video generation failed for topic %s", topic_id)
        async with SessionLocal() as s:
            topic = await s.get(Topic, topic_id)
            if topic is not None:
                topic.video_status, topic.video_detail = "failed", ""
                topic.video_error = "We couldn't create this video. Please try again."
                await s.commit()
