"""Prompt templates. Kept in one place so they're easy to review and tune."""

from __future__ import annotations

from collections.abc import Sequence

OUTLINE_SYSTEM = (
    "You are an expert teacher and curriculum designer. You organise a student's study material "
    "into a clear revision syllabus. You use only the material provided and never invent facts."
)

KIT_SYSTEM = (
    "You are an experienced examiner and tutor. You write accurate, exam-quality study material "
    "strictly from the source text you are given. You never add facts that are not in the source."
)

VERIFY_SYSTEM = (
    "You are a meticulous fact-checker for exam questions. You judge each item ONLY against the "
    "evidence provided with it. Use general knowledge only to interpret the evidence, never to override it."
)


def topic_range(char_count: int) -> tuple[int, int, str]:
    """How many topics/units suit a document of this size."""
    if char_count < 3_000:
        return 2, 3, "1 unit"
    if char_count < 12_000:
        return 3, 6, "1–2 units"
    if char_count < 40_000:
        return 4, 9, "2–3 units"
    if char_count < 100_000:
        return 6, 12, "3–5 units"
    return 8, 14, "3–6 units"


def format_chunks(chunks: Sequence[tuple[int, str, str]], max_chars: int | None = None) -> str:
    """chunks: (id, location label, text)."""
    parts: list[str] = []
    used = 0
    for cid, loc, text in chunks:
        block = f"[C{cid} | {loc}]\n{text}"
        if max_chars is not None and used + len(block) > max_chars and parts:
            parts.append("[… remaining material omitted for length …]")
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def outline_prompt(material: str, char_count: int) -> str:
    lo, hi, units = topic_range(char_count)
    return f"""Below is a student's study material, split into numbered chunks. Each chunk starts with [C<id> | <location>].

Organise it into units and topics for revision.

Rules:
- Create {lo}–{hi} topics in total, grouped into {units}. Units are broad themes (like chapters); topics are specific, teachable ideas a student could be examined on (e.g. "Light-dependent reactions" — never "Introduction", "Overview" or "Miscellaneous").
- Follow the order of the material.
- For every topic give: a clear title (max 8 words), a 1–2 sentence summary, 3–5 key points (short, exam-ready facts), and chunk_ids = the ids of every chunk that contains material for that topic.
- Every chunk with real subject matter must belong to at least one topic. Ignore chunks that only contain a table of contents, references, acknowledgements or administrative details.
- Use only information from the material. Do not invent facts.
- document_title: a concise title for the whole material (max 10 words). overview: 2–3 sentences on what the material covers.

MATERIAL:
{material}"""


def kit_prompt(
    *,
    topic_title: str,
    unit_title: str,
    doc_title: str,
    summary: str,
    source: str,
    n_mcq: int = 8,
    n_short: int = 2,
    n_long: int = 2,
    n_beats: int = 6,
) -> str:
    return f"""Create a study kit for the topic "{topic_title}" (unit: "{unit_title}", from "{doc_title}").

Topic summary: {summary}

SOURCE — numbered chunks; use ONLY this material:
{source}

Produce:

1. mcqs — exactly {n_mcq} multiple-choice questions.
   - Test understanding, not trivia: mix recall, application and "which statement is correct" styles. Difficulty mix: about 30% easy, 40% medium, 30% hard.
   - Exactly 4 options with one clearly correct answer. Distractors must be plausible, similar in length and style, and clearly wrong according to the source. Never use "All of the above" or "None of the above".
   - answer_index = the 0-based index of the correct option.
   - explanation: 1–2 sentences on why the answer is correct (and why a tempting distractor is wrong, if useful).
   - source_quote: copy a short passage (max 30 words) VERBATIM from the source that proves the answer — exactly the same words in the same order.
   - chunk_id: the numeric id of the chunk that contains that quote (e.g. 12 for [C12 …]).

2. qa — exactly {n_short + n_long} exam-style theory questions with model answers.
   - {n_short} with kind "short" (answer in 2–4 sentences) and {n_long} with kind "long" (answer in 120–220 words, using short paragraphs and "- " bullet points where helpful; **bold** key terms).
   - Answers must be complete and correct using only the source.
   - source_quote + chunk_id: the verbatim passage (max 30 words) that best supports the answer.

3. video — a narrated explainer of {n_beats} beats (about 60–90 seconds of speech in total), like a friendly tutor teaching the topic.
   - Beat 1: kind "title"; heading = the topic title; narration introduces what the viewer will learn.
   - Middle beats: mix the kinds "bullets" (2–4 short points), "definition" (term + definition), "quote" (one key sentence copied verbatim from the source) and "steps" (2–4 ordered steps, for processes).
   - Last beat: kind "summary" with exactly 3 key takeaways in points.
   - heading max 7 words; each point max 12 words; narration = 1–3 conversational sentences that explain the idea rather than reading the slide aloud.
   - Leave fields a beat doesn't use as "" or []. chunk_id = the main source chunk for the beat (0 for the title beat).

4. youtube_query — a precise YouTube search query (4–8 words) that would find a good explanation video for this topic."""


def verify_prompt(items: list[str]) -> str:
    joined = "\n\n".join(items)
    return f"""Check each item below against its evidence and return one result per item.

Verdicts:
- "supported": the evidence supports the marked answer. For multiple choice, the marked option must be correct AND no other option may also be correct according to the evidence.
- "ambiguous": more than one option could reasonably be correct, or the question is unclear.
- "unsupported": the evidence contradicts the answer, or the answer's central claim is not in the evidence.

Be strict but fair: different wording is fine when the meaning matches. For theory answers, extra correct detail is acceptable as long as the central claim is supported and nothing contradicts the evidence.

Return JSON: {{"results": [{{"id": "<item id>", "verdict": "supported|unsupported|ambiguous", "note": "<max 15 words>"}}]}}

ITEMS:
{joined}"""
