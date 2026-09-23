"""Structured-output schemas the models must fill in.

Kept deliberately flat and simple: they are sent to Gemini as `response_schema`, and to
Groq as a JSON schema in the prompt.
"""

from typing import Literal

from pydantic import BaseModel


# ---- Outline (units -> topics) -------------------------------------------------------


class OutlineTopic(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    chunk_ids: list[int]


class OutlineUnit(BaseModel):
    title: str
    topics: list[OutlineTopic]


class Outline(BaseModel):
    document_title: str
    overview: str
    units: list[OutlineUnit]


# ---- Study kit (per topic) --------------------------------------------------------------


class MCQ(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    difficulty: Literal["easy", "medium", "hard"]
    source_quote: str
    chunk_id: int


class QA(BaseModel):
    question: str
    answer: str
    kind: Literal["short", "long"]
    source_quote: str
    chunk_id: int


class Beat(BaseModel):
    kind: Literal["title", "bullets", "quote", "definition", "steps", "summary"]
    heading: str
    points: list[str]
    quote: str
    term: str
    definition: str
    narration: str
    chunk_id: int


class StudyKit(BaseModel):
    mcqs: list[MCQ]
    qa: list[QA]
    video: list[Beat]
    youtube_query: str


# ---- Verification ------------------------------------------------------------------------


class Verdict(BaseModel):
    id: str
    verdict: Literal["supported", "unsupported", "ambiguous"]
    note: str


class VerificationResult(BaseModel):
    results: list[Verdict]
