"""Response models for the public API (also documents the API in /docs)."""

from datetime import datetime

from pydantic import BaseModel


class TopicSummary(BaseModel):
    id: str
    idx: int
    title: str
    summary: str
    loc_label: str
    kit_status: str
    kit_error: str | None
    video_status: str
    question_count: int
    verified_count: int
    qa_count: int


class UnitOut(BaseModel):
    idx: int
    title: str
    topics: list[TopicSummary]


class Counts(BaseModel):
    topics: int
    ready_topics: int
    failed_topics: int
    questions: int
    verified_questions: int
    qa: int
    videos_ready: int


class DocumentOut(BaseModel):
    id: str
    title: str
    filename: str
    file_type: str
    source_label: str
    page_count: int
    status: str
    stage: str
    stage_detail: str
    error: str | None
    summary: str
    created_at: datetime
    counts: Counts
    units: list[UnitOut]
    duplicate: bool = False


class QuestionOut(BaseModel):
    id: int
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    difficulty: str
    source_quote: str
    source_loc: str
    verification: str


class MockQuestionOut(QuestionOut):
    topic_id: str
    topic_title: str


class QAOut(BaseModel):
    id: int
    question: str
    answer: str
    kind: str
    source_quote: str
    source_loc: str
    verification: str


class Scene(BaseModel):
    heading: str
    narration: str
    start: float | None = None
    end: float | None = None


class VideoOut(BaseModel):
    status: str
    detail: str
    error: str | None
    duration: float | None
    size_bytes: int | None
    url: str | None
    captions_url: str | None
    poster_url: str | None = None
    scenes: list[Scene]
    narrated: bool


class YouTubeItem(BaseModel):
    video_id: str
    title: str
    channel: str
    thumbnail: str
    url: str


class YouTubeLink(BaseModel):
    label: str
    query: str
    url: str


class YouTubeOut(BaseModel):
    mode: str
    query: str
    items: list[YouTubeItem]
    links: list[YouTubeLink]


class TopicNav(BaseModel):
    id: str
    title: str


class TopicDetail(BaseModel):
    id: str
    document_id: str
    document_title: str
    source_label: str
    unit_title: str
    idx: int
    total_topics: int
    title: str
    summary: str
    key_points: list[str]
    loc_label: str
    kit_status: str
    kit_error: str | None
    questions: list[QuestionOut]
    qa: list[QAOut]
    video: VideoOut
    youtube: YouTubeOut
    prev_topic: TopicNav | None
    next_topic: TopicNav | None


class MockTestOut(BaseModel):
    document_id: str
    document_title: str
    questions: list[MockQuestionOut]


class HealthOut(BaseModel):
    status: str
    database: bool
    generator: str
    verifier: str
    video: bool
    youtube: str
    version: str
