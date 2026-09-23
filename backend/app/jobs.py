"""In-process background job manager.

Render's free tier has no background workers, so jobs run inside the web process:
- one document worker (LLM-bound, rate-limited anyway),
- one video worker (CPU-bound; one at a time protects the 0.1-CPU instance),
- a keep-alive loop that pings our own public URL while work is pending, so the
  instance doesn't spin down mid-job (Render sets RENDER_EXTERNAL_URL for us).

State lives in the database, so `recover()` can resume everything after a restart.
"""

from __future__ import annotations

import asyncio
import itertools
import logging

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Document, Topic
from app.pipeline import generate_video, process_document

log = logging.getLogger(__name__)


class JobManager:
    def __init__(self) -> None:
        self.doc_queue: asyncio.Queue[str] = asyncio.Queue()
        self.video_queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
        self._queued_docs: set[str] = set()
        self._video_priority: dict[str, int] = {}
        self._counter = itertools.count()
        self._tasks: list[asyncio.Task] = []
        self._running = 0

    # ---- public API -------------------------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._running > 0 or not self.doc_queue.empty() or not self.video_queue.empty()

    def enqueue_document(self, document_id: str) -> None:
        if document_id not in self._queued_docs:
            self._queued_docs.add(document_id)
            self.doc_queue.put_nowait(document_id)

    def enqueue_video(self, topic_id: str, priority: int = 10) -> None:
        """Lower priority value runs sooner; a user explicitly asking for a video uses 0."""
        current = self._video_priority.get(topic_id)
        if current is not None and current <= priority:
            return
        self._video_priority[topic_id] = priority
        self.video_queue.put_nowait((priority, next(self._counter), topic_id))

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._doc_worker(), name="doc-worker"),
            asyncio.create_task(self._video_worker(), name="video-worker"),
            asyncio.create_task(self._keepalive(), name="keepalive"),
        ]
        await self.recover()

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def recover(self) -> None:
        async with SessionLocal() as s:
            docs = (
                await s.scalars(
                    select(Document.id).where(Document.status.in_(("queued", "processing"))).order_by(Document.created_at)
                )
            ).all()
            videos = (
                await s.scalars(
                    select(Topic.id).where(Topic.video_status.in_(("queued", "generating")), Topic.kit_status == "ready")
                )
            ).all()
        for doc_id in docs:
            self.enqueue_document(doc_id)
        for topic_id in videos:
            self.enqueue_video(topic_id, priority=5)
        if docs or videos:
            log.info("Recovered %d document job(s) and %d video job(s)", len(docs), len(videos))

    # ---- workers --------------------------------------------------------------------------------
    async def _doc_worker(self) -> None:
        while True:
            document_id = await self.doc_queue.get()
            self._queued_docs.discard(document_id)
            self._running += 1
            try:
                await process_document(document_id, enqueue_video=self.enqueue_video)
            except Exception:  # noqa: BLE001 — a worker must never die
                log.exception("Unhandled error processing document %s", document_id)
            finally:
                self._running -= 1
                self.doc_queue.task_done()

    async def _video_worker(self) -> None:
        while True:
            priority, _, topic_id = await self.video_queue.get()
            if self._video_priority.get(topic_id) != priority:
                self.video_queue.task_done()  # stale entry superseded by a higher-priority request
                continue
            self._video_priority.pop(topic_id, None)
            self._running += 1
            try:
                await generate_video(topic_id)
            except Exception:  # noqa: BLE001
                log.exception("Unhandled error generating video %s", topic_id)
            finally:
                self._running -= 1
                self.video_queue.task_done()

    async def _keepalive(self) -> None:
        url = get_settings().render_external_url.rstrip("/")
        if not url:
            return
        async with httpx.AsyncClient(timeout=20) as client:
            while True:
                await asyncio.sleep(240)
                if self.busy:
                    try:
                        await client.get(f"{url}/api/health")
                    except httpx.HTTPError as exc:
                        log.debug("keep-alive ping failed: %s", exc)

    async def wait_idle(self, timeout: float = 60) -> None:
        """Test helper: wait until all queued work has finished."""
        async def _wait() -> None:
            while self.busy:
                await asyncio.sleep(0.05)

        await asyncio.wait_for(_wait(), timeout)


jobs = JobManager()
