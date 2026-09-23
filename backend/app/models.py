"""ORM models.

Everything the app needs to survive a restart lives here — including generated videos —
because free-tier hosts have an ephemeral filesystem.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(300))
    file_type: Mapped[str] = mapped_column(String(10))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_label: Mapped[str] = mapped_column(String(20), default="page")  # page | slide | section
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    # queued -> processing -> ready | failed
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    # parsing -> outlining -> building -> done
    stage: Mapped[str] = mapped_column(String(20), default="outlining")
    stage_detail: Mapped[str] = mapped_column(String(300), default="Queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Chunk.idx"
    )
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Topic.idx"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)  # 1-based id shown to the LLM as C<idx>
    loc_start: Mapped[int] = mapped_column(Integer)
    loc_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    unit_idx: Mapped[int] = mapped_column(Integer, default=0)
    unit_title: Mapped[str] = mapped_column(String(300), default="")
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    key_points: Mapped[list] = mapped_column(JSON, default=list)
    chunk_idxs: Mapped[list] = mapped_column(JSON, default=list)
    loc_label: Mapped[str] = mapped_column(String(60), default="")

    # pending -> generating -> ready | failed
    kit_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    kit_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    youtube_query: Mapped[str] = mapped_column(String(300), default="")
    youtube: Mapped[dict] = mapped_column(JSON, default=dict)

    # none -> queued -> generating -> ready | failed
    video_status: Mapped[str] = mapped_column(String(20), default="none", index=True)
    video_detail: Mapped[str] = mapped_column(String(200), default="")
    video_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_script: Mapped[list] = mapped_column(JSON, default=list)

    document: Mapped[Document] = relationship(back_populates="topics")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="Question.idx"
    )
    qa_items: Mapped[list["QAItem"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="QAItem.idx"
    )
    video: Mapped["VideoAsset | None"] = relationship(
        back_populates="topic", cascade="all, delete-orphan", uselist=False
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    answer_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")
    source_quote: Mapped[str] = mapped_column(Text, default="")
    source_loc: Mapped[str] = mapped_column(String(40), default="")
    # verified (quote found + independent model agrees) | quote_checked (quote found only)
    verification: Mapped[str] = mapped_column(String(20), default="quote_checked")

    topic: Mapped[Topic] = relationship(back_populates="questions")


class QAItem(Base):
    __tablename__ = "qa_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(10), default="short")
    source_quote: Mapped[str] = mapped_column(Text, default="")
    source_loc: Mapped[str] = mapped_column(String(40), default="")
    verification: Mapped[str] = mapped_column(String(20), default="quote_checked")

    topic: Mapped[Topic] = relationship(back_populates="qa_items")


class VideoAsset(Base):
    __tablename__ = "video_assets"

    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    mp4: Mapped[bytes] = mapped_column(LargeBinary)
    poster: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    topic: Mapped[Topic] = relationship(back_populates="video")
