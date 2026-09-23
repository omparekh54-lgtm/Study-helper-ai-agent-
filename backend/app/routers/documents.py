"""Document endpoints: upload, status/dashboard, retry, delete, study pack and mock test."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_models import Counts, DocumentOut, MockQuestionOut, MockTestOut, TopicSummary, UnitOut
from app.config import get_settings
from app.db import get_session
from app.jobs import jobs
from app.models import Chunk, Document, QAItem, Question, Topic, VideoAsset
from app.routers._util import download_response
from app.services.exports import QAExport, TopicExport, study_pack_pdf
from app.services.parsing import ParseError, parse_document

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

_upload_log: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    for header in ("cf-connecting-ip", "true-client-ip"):
        if request.headers.get(header):
            return request.headers[header].strip()
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> None:
    limit = get_settings().uploads_per_ip_per_hour
    now = time.time()
    log_ = _upload_log[ip]
    while log_ and now - log_[0] > 3600:
        log_.popleft()
    if len(log_) >= limit:
        minutes = int((3600 - (now - log_[0])) // 60) + 1
        raise HTTPException(429, f"You've uploaded a lot of documents recently. Please try again in about {minutes} minutes.")
    log_.append(now)


def title_from_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\(\d+\)|\bfinal\b|\bcopy\b", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\s+", " ", stem).strip()
    return (stem[:1].upper() + stem[1:]) if stem else "Untitled document"


async def build_document_out(session: AsyncSession, doc: Document, duplicate: bool = False) -> DocumentOut:
    topics = (await session.scalars(select(Topic).where(Topic.document_id == doc.id).order_by(Topic.idx))).all()
    topic_ids = [t.id for t in topics]
    q_counts: dict[str, tuple[int, int]] = {}
    qa_counts: dict[str, int] = {}
    videos_ready = 0
    if topic_ids:
        rows = await session.execute(
            select(
                Question.topic_id,
                func.count(),
                func.sum(case((Question.verification == "verified", 1), else_=0)),
            )
            .where(Question.topic_id.in_(topic_ids))
            .group_by(Question.topic_id)
        )
        q_counts = {tid: (n, int(v or 0)) for tid, n, v in rows}
        rows = await session.execute(
            select(QAItem.topic_id, func.count()).where(QAItem.topic_id.in_(topic_ids)).group_by(QAItem.topic_id)
        )
        qa_counts = dict(rows.all())
        videos_ready = sum(1 for t in topics if t.video_status == "ready")

    units: dict[int, UnitOut] = {}
    for t in topics:
        unit = units.setdefault(t.unit_idx, UnitOut(idx=t.unit_idx, title=t.unit_title, topics=[]))
        n, v = q_counts.get(t.id, (0, 0))
        unit.topics.append(
            TopicSummary(
                id=t.id, idx=t.idx, title=t.title, summary=t.summary, loc_label=t.loc_label,
                kit_status=t.kit_status, kit_error=t.kit_error, video_status=t.video_status,
                question_count=n, verified_count=v, qa_count=qa_counts.get(t.id, 0),
            )
        )

    counts = Counts(
        topics=len(topics),
        ready_topics=sum(1 for t in topics if t.kit_status == "ready"),
        failed_topics=sum(1 for t in topics if t.kit_status == "failed"),
        questions=sum(n for n, _ in q_counts.values()),
        verified_questions=sum(v for _, v in q_counts.values()),
        qa=sum(qa_counts.values()),
        videos_ready=videos_ready,
    )
    return DocumentOut(
        id=doc.id, title=doc.title, filename=doc.filename, file_type=doc.file_type, source_label=doc.source_label,
        page_count=doc.page_count, status=doc.status, stage=doc.stage, stage_detail=doc.stage_detail,
        error=doc.error, summary=doc.summary, created_at=doc.created_at, counts=counts,
        units=[units[k] for k in sorted(units)], duplicate=duplicate,
    )


async def _get_doc(session: AsyncSession, document_id: str) -> Document:
    doc = await session.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found. It may have been deleted.")
    return doc


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request, file: UploadFile, response: Response, session: AsyncSession = Depends(get_session)
) -> DocumentOut:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"That file is larger than {settings.max_upload_mb} MB. Try a smaller file or split it.")
    filename = (file.filename or "document").strip()[:200]
    content_hash = hashlib.sha256(data).hexdigest()

    existing = await session.scalar(
        select(Document)
        .where(Document.content_hash == content_hash, Document.status != "failed")
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        response.status_code = 200
        return await build_document_out(session, existing, duplicate=True)

    _check_rate_limit(client_ip(request))
    try:
        parsed = await asyncio.to_thread(
            parse_document, filename, data, max_pages=settings.max_pages, max_chars=settings.max_chars
        )
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    doc = Document(
        title=title_from_filename(filename), filename=filename, file_type=parsed.file_type,
        content_hash=content_hash, source_label=parsed.source_label, page_count=len(parsed.pages),
        char_count=parsed.char_count, status="queued", stage="outlining", stage_detail="Queued",
    )
    session.add(doc)
    await session.flush()
    session.add_all(
        Chunk(document_id=doc.id, idx=c.idx, loc_start=c.loc_start, loc_end=c.loc_end, text=c.text) for c in parsed.chunks
    )
    await session.commit()
    jobs.enqueue_document(doc.id)
    log.info("Accepted %s (%s, %d %ss, %d chunks)", doc.id, parsed.file_type, len(parsed.pages), parsed.source_label, len(parsed.chunks))
    return await build_document_out(session, doc)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, session: AsyncSession = Depends(get_session)) -> DocumentOut:
    return await build_document_out(session, await _get_doc(session, document_id))


@router.post("/{document_id}/retry", response_model=DocumentOut)
async def retry_document(document_id: str, session: AsyncSession = Depends(get_session)) -> DocumentOut:
    doc = await _get_doc(session, document_id)
    failed = (await session.scalars(select(Topic).where(Topic.document_id == doc.id, Topic.kit_status == "failed"))).all()
    if doc.status == "failed" or failed:
        for t in failed:
            t.kit_status, t.kit_error = "pending", None
        doc.status, doc.error, doc.stage_detail = "queued", None, "Queued for another try"
        await session.commit()
        jobs.enqueue_document(doc.id)
    return await build_document_out(session, doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    doc = await _get_doc(session, document_id)
    topic_ids = select(Topic.id).where(Topic.document_id == doc.id)
    for model in (VideoAsset, Question, QAItem):
        await session.execute(delete(model).where(model.topic_id.in_(topic_ids)))
    await session.execute(delete(Topic).where(Topic.document_id == doc.id))
    await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    await session.execute(delete(Document).where(Document.id == doc.id))
    await session.commit()
    return Response(status_code=204)


@router.get("/{document_id}/study-pack.pdf")
async def study_pack(document_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    doc = await _get_doc(session, document_id)
    topics = (
        await session.scalars(
            select(Topic).where(Topic.document_id == doc.id, Topic.kit_status == "ready").order_by(Topic.idx)
        )
    ).all()
    if not topics:
        raise HTTPException(409, "The study pack isn't ready yet.")
    exports = []
    for t in topics:
        qa = (await session.scalars(select(QAItem).where(QAItem.topic_id == t.id).order_by(QAItem.idx))).all()
        exports.append(
            TopicExport(
                title=t.title, unit=t.unit_title, summary=t.summary, key_points=list(t.key_points),
                qa=[QAExport(q.question, q.answer, q.kind, q.source_loc, q.verification) for q in qa],
            )
        )
    pdf = await asyncio.to_thread(study_pack_pdf, doc.title, doc.summary, exports)
    return download_response(pdf, f"{doc.title} - study pack.pdf", "application/pdf")


@router.get("/{document_id}/mock-test", response_model=MockTestOut)
async def mock_test(document_id: str, count: int = 20, session: AsyncSession = Depends(get_session)) -> MockTestOut:
    doc = await _get_doc(session, document_id)
    count = max(5, min(count, 50))
    rows = (
        await session.execute(
            select(Question, Topic.title)
            .join(Topic, Topic.id == Question.topic_id)
            .where(Topic.document_id == doc.id, Topic.kit_status == "ready")
            .order_by(Topic.idx, Question.idx)
        )
    ).all()
    if not rows:
        raise HTTPException(409, "No questions are ready yet.")
    by_topic: dict[str, list] = defaultdict(list)
    for q, topic_title in rows:
        by_topic[q.topic_id].append((q, topic_title))
    rng = random.Random()
    for items in by_topic.values():
        rng.shuffle(items)
    # Round-robin across topics so the test covers the whole syllabus.
    picked = []
    while len(picked) < count and any(by_topic.values()):
        for items in by_topic.values():
            if items and len(picked) < count:
                picked.append(items.pop())
    rng.shuffle(picked)
    return MockTestOut(
        document_id=doc.id,
        document_title=doc.title,
        questions=[
            MockQuestionOut(
                id=q.id, question=q.question, options=q.options, answer_index=q.answer_index,
                explanation=q.explanation, difficulty=q.difficulty, source_quote=q.source_quote,
                source_loc=q.source_loc, verification=q.verification, topic_id=q.topic_id, topic_title=title,
            )
            for q, title in picked
        ],
    )


