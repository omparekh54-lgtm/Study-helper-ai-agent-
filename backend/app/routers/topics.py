"""Topic endpoints: study kit, video (+captions), practice PDFs, retry."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_models import QAOut, QuestionOut, Scene, TopicDetail, TopicNav, VideoOut, YouTubeOut
from app.db import get_session
from app.jobs import jobs
from app.models import Document, QAItem, Question, Topic, VideoAsset
from app.routers._util import BytesLRU, download_response, range_response
from app.services.exports import MCQExport, QAExport, TopicExport, quiz_pdf, study_pack_pdf
from app.services.video.producer import build_vtt

router = APIRouter(prefix="/api/topics", tags=["topics"])
_video_cache = BytesLRU(max_items=6)


async def _get_topic(session: AsyncSession, topic_id: str) -> Topic:
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(404, "Topic not found.")
    return topic


def _video_out(topic: Topic, asset_meta: tuple[float, int] | None) -> VideoOut:
    scenes = [
        Scene(heading=b.get("heading", ""), narration=b.get("narration", ""), start=b.get("start"), end=b.get("end"))
        for b in (topic.video_script or [])
    ]
    ready = topic.video_status == "ready" and asset_meta is not None
    return VideoOut(
        status=topic.video_status if topic.video_status != "ready" or ready else "none",
        detail=topic.video_detail if topic.video_status != "ready" else "",
        error=topic.video_error,
        duration=asset_meta[0] if ready else None,
        size_bytes=asset_meta[1] if ready else None,
        url=f"/api/topics/{topic.id}/video.mp4" if ready else None,
        captions_url=f"/api/topics/{topic.id}/video.vtt" if ready else None,
        poster_url=f"/api/topics/{topic.id}/poster.jpg" if ready else None,
        scenes=scenes,
        narrated=topic.video_detail != "silent" if ready else True,
    )


@router.get("/{topic_id}", response_model=TopicDetail)
async def get_topic(topic_id: str, session: AsyncSession = Depends(get_session)) -> TopicDetail:
    topic = await _get_topic(session, topic_id)
    doc = await session.get(Document, topic.document_id)
    questions = (await session.scalars(select(Question).where(Question.topic_id == topic.id).order_by(Question.idx))).all()
    qa = (await session.scalars(select(QAItem).where(QAItem.topic_id == topic.id).order_by(QAItem.idx))).all()
    asset = (
        await session.execute(select(VideoAsset.duration_s, VideoAsset.size_bytes).where(VideoAsset.topic_id == topic.id))
    ).first()
    siblings = (
        await session.execute(select(Topic.id, Topic.title, Topic.idx).where(Topic.document_id == topic.document_id).order_by(Topic.idx))
    ).all()
    pos = next(i for i, s in enumerate(siblings) if s.id == topic.id)
    prev_t = siblings[pos - 1] if pos > 0 else None
    next_t = siblings[pos + 1] if pos + 1 < len(siblings) else None
    yt = topic.youtube or {}

    return TopicDetail(
        id=topic.id,
        document_id=topic.document_id,
        document_title=doc.title,
        source_label=doc.source_label,
        unit_title=topic.unit_title,
        idx=topic.idx,
        total_topics=len(siblings),
        title=topic.title,
        summary=topic.summary,
        key_points=list(topic.key_points or []),
        loc_label=topic.loc_label,
        kit_status=topic.kit_status,
        kit_error=topic.kit_error,
        questions=[
            QuestionOut(
                id=q.id, question=q.question, options=q.options, answer_index=q.answer_index, explanation=q.explanation,
                difficulty=q.difficulty, source_quote=q.source_quote, source_loc=q.source_loc, verification=q.verification,
            )
            for q in questions
        ],
        qa=[
            QAOut(
                id=a.id, question=a.question, answer=a.answer, kind=a.kind, source_quote=a.source_quote,
                source_loc=a.source_loc, verification=a.verification,
            )
            for a in qa
        ],
        video=_video_out(topic, (asset.duration_s, asset.size_bytes) if asset else None),
        youtube=YouTubeOut(
            mode=yt.get("mode", "search"), query=topic.youtube_query, items=yt.get("items", []), links=yt.get("links", [])
        ),
        prev_topic=TopicNav(id=prev_t.id, title=prev_t.title) if prev_t else None,
        next_topic=TopicNav(id=next_t.id, title=next_t.title) if next_t else None,
    )


@router.post("/{topic_id}/video", response_model=VideoOut)
async def request_video(topic_id: str, session: AsyncSession = Depends(get_session)) -> VideoOut:
    """Ask for this topic's video now (jumps the background queue)."""
    topic = await _get_topic(session, topic_id)
    if topic.kit_status != "ready":
        raise HTTPException(409, "This topic's study kit isn't ready yet.")
    asset = (
        await session.execute(select(VideoAsset.duration_s, VideoAsset.size_bytes).where(VideoAsset.topic_id == topic.id))
    ).first()
    if topic.video_status in ("none", "failed") or (topic.video_status == "ready" and asset is None):
        topic.video_status, topic.video_detail, topic.video_error = "queued", "Waiting in line", None
        await session.commit()
    if topic.video_status in ("queued",):
        jobs.enqueue_video(topic.id, priority=0)
    return _video_out(topic, (asset.duration_s, asset.size_bytes) if asset else None)


async def _load_video(session: AsyncSession, topic_id: str) -> tuple[bytes, str]:
    row = (
        await session.execute(select(VideoAsset.created_at).where(VideoAsset.topic_id == topic_id))
    ).first()
    if row is None:
        raise HTTPException(404, "Video not ready yet.")
    etag = f'"{topic_id}-{int(row.created_at.timestamp())}"'
    data = _video_cache.get(etag)
    if data is None:
        data = await session.scalar(select(VideoAsset.mp4).where(VideoAsset.topic_id == topic_id))
        _video_cache.put(etag, data)
    return data, etag


@router.get("/{topic_id}/video.mp4")
async def video_file(topic_id: str, request: Request, download: bool = False, session: AsyncSession = Depends(get_session)) -> Response:
    data, etag = await _load_video(session, topic_id)
    if download:
        topic = await _get_topic(session, topic_id)
        return download_response(data, f"{topic.title} - video overview.mp4", "video/mp4")
    return range_response(data, request.headers.get("range"), "video/mp4", etag)


@router.get("/{topic_id}/poster.jpg")
async def video_poster(topic_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    poster = await session.scalar(select(VideoAsset.poster).where(VideoAsset.topic_id == topic_id))
    if not poster:
        raise HTTPException(404, "Poster not available.")
    return Response(poster, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/{topic_id}/video.vtt")
async def video_captions(topic_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    topic = await _get_topic(session, topic_id)
    timeline = [b for b in (topic.video_script or []) if b.get("start") is not None]
    if not timeline:
        raise HTTPException(404, "Captions not ready yet.")
    return Response(build_vtt(timeline), media_type="text/vtt", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/{topic_id}/quiz.pdf")
async def topic_quiz_pdf(topic_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    topic = await _get_topic(session, topic_id)
    doc = await session.get(Document, topic.document_id)
    questions = (await session.scalars(select(Question).where(Question.topic_id == topic.id).order_by(Question.idx))).all()
    if not questions:
        raise HTTPException(409, "No questions are ready for this topic yet.")
    items = [MCQExport(q.question, q.options, q.answer_index, q.explanation, q.source_loc, q.difficulty) for q in questions]
    pdf = await asyncio.to_thread(quiz_pdf, doc.title, topic.title, items)
    return download_response(pdf, f"{topic.title} - practice test.pdf", "application/pdf")


@router.get("/{topic_id}/qa.pdf")
async def topic_qa_pdf(topic_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    topic = await _get_topic(session, topic_id)
    doc = await session.get(Document, topic.document_id)
    qa = (await session.scalars(select(QAItem).where(QAItem.topic_id == topic.id).order_by(QAItem.idx))).all()
    if not qa:
        raise HTTPException(409, "No Q&A is ready for this topic yet.")
    export = TopicExport(
        title=topic.title, unit=topic.unit_title, summary=topic.summary, key_points=list(topic.key_points),
        qa=[QAExport(a.question, a.answer, a.kind, a.source_loc, a.verification) for a in qa],
    )
    pdf = await asyncio.to_thread(study_pack_pdf, f"{topic.title} — {doc.title}", "", [export])
    return download_response(pdf, f"{topic.title} - Q&A.pdf", "application/pdf")


@router.post("/{topic_id}/retry", response_model=TopicNav)
async def retry_topic(topic_id: str, session: AsyncSession = Depends(get_session)) -> TopicNav:
    topic = await _get_topic(session, topic_id)
    if topic.kit_status not in ("failed", "ready"):
        return TopicNav(id=topic.id, title=topic.title)
    doc = await session.get(Document, topic.document_id)
    await session.execute(delete(VideoAsset).where(VideoAsset.topic_id == topic.id))
    topic.kit_status, topic.kit_error = "pending", None
    topic.video_status, topic.video_detail, topic.video_error = "none", "", None
    doc.status, doc.error, doc.stage_detail = "queued", None, "Regenerating a topic"
    await session.commit()
    jobs.enqueue_document(doc.id)
    return TopicNav(id=topic.id, title=topic.title)
