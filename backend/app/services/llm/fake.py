"""Deterministic offline stand-in for Gemini/Groq.

Used by the test-suite and for running the whole app without API keys (LLM_MODE=fake).
It builds its outputs from the real source text, so quotes are genuinely verbatim and the
deterministic grounding checks are exercised exactly as in production.
"""

from __future__ import annotations

import asyncio
import re

from app.services.llm.base import T
from app.services.llm.schemas import (
    MCQ,
    QA,
    Beat,
    Outline,
    OutlineTopic,
    OutlineUnit,
    StudyKit,
    VerificationResult,
    Verdict,
)

_CHUNK_RE = re.compile(r"\[C(\d+) \| [^\]]*\]\n(.*?)(?=\n\n\[C\d+ \||\n\n\[…|\Z)", re.DOTALL)
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _chunks(prompt: str) -> list[tuple[int, str]]:
    return [(int(m.group(1)), m.group(2).strip()) for m in _CHUNK_RE.finditer(prompt)]


def _sentences(text: str) -> list[str]:
    out = []
    for s in _SENT_RE.split(text.replace("\n", " ")):
        s = s.strip(" •-")
        if 30 <= len(s) <= 400 and len(s.split()) >= 6:
            out.append(s)
    return out


def _words(s: str, n: int) -> str:
    return " ".join(s.split()[:n])


def _title_from(text: str) -> str:
    first = text.strip().split("\n", 1)[0]
    words = re.sub(r"[^\w\s-]", "", first).split()
    return " ".join(words[:6]).title() or "Key Ideas"


class FakeGenerator:
    def __init__(self, name: str = "fake"):
        self.name = name

    async def generate_json(self, *, system: str, prompt: str, schema: type[T], max_output_tokens: int = 8192) -> T:
        await asyncio.sleep(0.01)
        if schema is Outline:
            return self._outline(prompt)  # type: ignore[return-value]
        if schema is StudyKit:
            return self._kit(prompt)  # type: ignore[return-value]
        if schema is VerificationResult:
            return self._verify(prompt)  # type: ignore[return-value]
        raise NotImplementedError(schema)

    # ------------------------------------------------------------------------------------
    def _outline(self, prompt: str) -> Outline:
        chunks = _chunks(prompt)
        groups = [chunks[i : i + 2] for i in range(0, len(chunks), 2)] or [[(1, "Material")]]
        topics = []
        for group in groups:
            text = " ".join(t for _, t in group)
            sents = _sentences(text) or [text[:120]]
            topics.append(
                OutlineTopic(
                    title=_title_from(group[0][1]),
                    summary=_words(sents[0], 30),
                    key_points=[_words(s, 12) for s in sents[:4]],
                    chunk_ids=[cid for cid, _ in group],
                )
            )
        units = [
            OutlineUnit(title=f"Unit {i // 3 + 1}: {topics[i].title}", topics=topics[i : i + 3])
            for i in range(0, len(topics), 3)
        ]
        return Outline(
            document_title=_title_from(chunks[0][1]) if chunks else "Study Notes",
            overview="These notes cover the key ideas in the uploaded material.",
            units=units,
        )

    def _kit(self, prompt: str) -> StudyKit:
        m = re.search(r'topic "(.+?)"', prompt)
        topic = m.group(1) if m else "this topic"
        chunks = _chunks(prompt.split("SOURCE", 1)[-1])
        pool: list[tuple[int, str]] = [(cid, s) for cid, text in chunks for s in _sentences(text)]
        if not pool:
            pool = [(chunks[0][0] if chunks else 1, "The material explains the core idea of this topic in detail.")]
        other = [s for _, s in pool]

        mcqs = []
        for i in range(min(10, max(4, len(pool)))):
            cid, sent = pool[i % len(pool)]
            distractors = [f"The material says the opposite: {_words(o, 10).lower()} is never true" for o in other[i + 1 : i + 4]]
            while len(distractors) < 3:
                distractors.append(f"None of the ideas in {topic} relate to this ({len(distractors)})")
            mcqs.append(
                MCQ(
                    question=f"Which statement about {topic} is supported by the material? ({i + 1})",
                    options=[_words(sent, 14), *distractors[:3]],
                    answer_index=0,
                    explanation=f"The material states: {_words(sent, 20)}.",
                    difficulty=("easy", "medium", "hard")[i % 3],
                    source_quote=_words(sent, 20),
                    chunk_id=cid,
                )
            )

        qa = []
        for i in range(6):
            cid, sent = pool[i % len(pool)]
            follow = " ".join(s for _, s in pool[i + 1 : i + 3])
            qa.append(
                QA(
                    question=f"Explain: {_words(sent, 8).rstrip('.,;:')}?",
                    answer=f"{sent} {follow}".strip() if i >= 3 else sent,
                    kind="long" if i >= 3 else "short",
                    source_quote=_words(sent, 20),
                    chunk_id=cid,
                )
            )

        s = [x for _, x in pool] + ["Review the key ideas regularly."] * 6
        cid0 = pool[0][0]
        video = [
            Beat(kind="title", heading=topic, points=[], quote="", term="", definition="",
                 narration=f"Let's explore {topic}. {_words(s[0], 18)}.", chunk_id=0),
            Beat(kind="bullets", heading="The big picture", points=[_words(x, 9) for x in s[:3]], quote="",
                 term="", definition="", narration=f"{s[0]}", chunk_id=cid0),
            Beat(kind="definition", heading="Key term", points=[], quote="", term=topic,
                 definition=_words(s[1], 22), narration=f"Here's a definition to remember. {s[1]}", chunk_id=cid0),
            Beat(kind="quote", heading="From your notes", points=[], quote=_words(s[2], 22), term="",
                 definition="", narration=f"Your notes put it this way. {s[2]}", chunk_id=cid0),
            Beat(kind="steps", heading="How it fits together", points=[_words(x, 8) for x in s[3:6]], quote="",
                 term="", definition="", narration=f"Step by step: {s[3]}", chunk_id=cid0),
            Beat(kind="summary", heading="Key takeaways", points=[_words(x, 9) for x in s[:3]], quote="",
                 term="", definition="", narration="Those are the key takeaways. Try the quiz to test yourself.", chunk_id=0),
        ]
        return StudyKit(mcqs=mcqs, qa=qa, video=video, youtube_query=f"{topic} explained")

    def _verify(self, prompt: str) -> VerificationResult:
        results = []
        for m in re.finditer(r"^\[(\w+)\]", prompt, re.MULTILINE):
            item_id = m.group(1)
            block = prompt[m.end() : prompt.find("\n\n[", m.end()) if prompt.find("\n\n[", m.end()) != -1 else None]
            verdict = "unsupported" if "UNSUPPORTED_MARKER" in block else "supported"
            results.append(Verdict(id=item_id, verdict=verdict, note="fake verifier"))
        return VerificationResult(results=results)
