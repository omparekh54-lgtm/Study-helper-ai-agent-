"""Two-layer grounding checks for generated study material.

Layer 1 (deterministic, free): every item must quote the source, and that quote must
actually appear in the document. Items that fail are dropped — no LLM involved.

Layer 2 (independent model): a different model family (Groq) checks that the quoted
evidence supports the marked answer and that no distractor is also correct.
Items it rejects are dropped; if the verifier is unavailable, items keep a
"quote_checked" label instead of "verified" so the UI stays honest.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import unicodedata
from dataclasses import dataclass, field

from app.services.llm import JSONGenerator, LLMError
from app.services.llm.prompts import VERIFY_SYSTEM, verify_prompt
from app.services.llm.schemas import MCQ, QA, VerificationResult

log = logging.getLogger(__name__)

_BANNED_OPTIONS = ("all of the above", "none of the above", "both a and b", "all of these", "none of these")


@dataclass
class SourceChunk:
    idx: int
    text: str
    loc: str  # human label, e.g. "p. 5"
    _norm: str = field(default="", repr=False)

    @property
    def norm(self) -> str:
        if not self._norm:
            self._norm = normalize(self.text)
        return self._norm


@dataclass
class Checked:
    item: MCQ | QA
    chunk: SourceChunk
    evidence: str
    verification: str = "quote_checked"  # -> "verified" when the independent model agrees


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐-―]", "-", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _shingles(words: list[str], n: int = 2) -> set[tuple[str, ...]]:
    if len(words) < n:
        return {tuple(words)} if words else set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def locate_quote(quote: str, chunks: dict[int, SourceChunk], preferred: int | None = None) -> SourceChunk | None:
    """Find the chunk that really contains `quote` (exact, or ≥75% of its word pairs)."""
    q = normalize(quote)
    if len(q.split()) < 3:
        return None
    order = sorted(chunks.values(), key=lambda c: (c.idx != preferred, c.idx))
    for chunk in order:
        if q in chunk.norm:
            return chunk
    q_sh = _shingles(q.split())
    best, best_score = None, 0.0
    for chunk in order:
        score = len(q_sh & _shingles(chunk.norm.split())) / len(q_sh)
        if score > best_score:
            best, best_score = chunk, score
    return best if best_score >= 0.75 else None


def evidence_window(text: str, quote: str, width: int) -> str:
    """A slice of the chunk around the quote, so the verifier sees context without the whole chunk."""
    words = quote.split()[:4]
    pos = -1
    if words:
        pattern = r"\W+".join(re.escape(w.strip(".,;:!?\"'()")) for w in words if w.strip(".,;:!?\"'()"))
        m = re.search(pattern, text, re.IGNORECASE) if pattern else None
        pos = m.start() if m else -1
    if pos == -1:
        return text[:width].strip()
    start = max(0, pos - width // 3)
    snippet = text[start : start + width].strip()
    return ("…" if start > 0 else "") + snippet + ("…" if start + width < len(text) else "")


def _valid_mcq(m: MCQ) -> bool:
    opts = [o.strip() for o in m.options]
    if len(opts) != 4 or any(not o for o in opts):
        return False
    if len({o.lower() for o in opts}) != 4:
        return False
    if any(any(b in o.lower() for b in _BANNED_OPTIONS) for o in opts):
        return False
    return 0 <= m.answer_index < 4 and bool(m.question.strip())


def shuffle_options(m: MCQ) -> MCQ:
    """Models over-use option A/B for the answer; shuffle deterministically to remove that bias."""
    seed = int(hashlib.sha256(m.question.encode()).hexdigest()[:8], 16)
    order = list(range(4))
    random.Random(seed).shuffle(order)
    options = [m.options[i].strip() for i in order]
    return m.model_copy(update={"options": options, "answer_index": order.index(m.answer_index)})


def grounding_check(mcqs: list[MCQ], qas: list[QA], chunks: dict[int, SourceChunk]) -> tuple[list[Checked], list[Checked]]:
    kept_m: list[Checked] = []
    for m in mcqs:
        if not _valid_mcq(m):
            continue
        chunk = locate_quote(m.source_quote, chunks, m.chunk_id)
        if chunk is None:
            continue
        kept_m.append(Checked(shuffle_options(m), chunk, evidence_window(chunk.text, m.source_quote, 400)))
    kept_q: list[Checked] = []
    for q in qas:
        if not q.question.strip() or len(q.answer.strip()) < 20:
            continue
        chunk = locate_quote(q.source_quote, chunks, q.chunk_id)
        if chunk is None:
            continue
        kept_q.append(Checked(q, chunk, evidence_window(chunk.text, q.source_quote, 700)))
    return kept_m, kept_q


def _render_mcq(key: str, c: Checked) -> str:
    m: MCQ = c.item  # type: ignore[assignment]
    letters = "ABCD"
    opts = " ".join(f"{letters[i]}) {o}" for i, o in enumerate(m.options))
    return (
        f"[{key}] Multiple choice\nQuestion: {m.question}\nOptions: {opts}\n"
        f"Marked answer: {letters[m.answer_index]}) {m.options[m.answer_index]}\n"
        f'Evidence ({c.chunk.loc}): "{c.evidence}"'
    )


def _render_qa(key: str, c: Checked) -> str:
    q: QA = c.item  # type: ignore[assignment]
    return f'[{key}] Theory question\nQuestion: {q.question}\nAnswer: {q.answer}\nEvidence ({c.chunk.loc}): "{c.evidence}"'


async def _run_verifier(verifier: JSONGenerator, rendered: dict[str, str]) -> dict[str, str]:
    if not rendered:
        return {}
    result = await verifier.generate_json(
        system=VERIFY_SYSTEM,
        prompt=verify_prompt(list(rendered.values())),
        schema=VerificationResult,
        max_output_tokens=1500,
    )
    return {r.id.strip("[] "): r.verdict for r in result.results}


async def verify_kit(
    mcqs: list[MCQ],
    qas: list[QA],
    chunks: dict[int, SourceChunk],
    verifier: JSONGenerator | None,
    max_mcq: int = 10,
    max_qa: int = 6,
) -> tuple[list[Checked], list[Checked]]:
    kept_m, kept_q = grounding_check(mcqs, qas, chunks)
    log.info("Grounding check kept %d/%d MCQs and %d/%d Q&A", len(kept_m), len(mcqs), len(kept_q), len(qas))

    if verifier is not None:
        groups = [(kept_m, _render_mcq, "m"), (kept_q, _render_qa, "q")]
        rendered_groups = [
            {f"{prefix}{i + 1}": render(f"{prefix}{i + 1}", c) for i, c in enumerate(items)}
            for items, render, prefix in groups
        ]
        # Both checks go out at once instead of one after the other.
        outcomes = await asyncio.gather(
            *(_run_verifier(verifier, rendered) for rendered in rendered_groups), return_exceptions=True
        )
        for (items, _render, prefix), verdicts in zip(groups, outcomes):
            if isinstance(verdicts, LLMError):
                log.warning("Verifier unavailable, keeping quote-checked items: %s", verdicts)
                continue
            if isinstance(verdicts, BaseException):
                raise verdicts
            survivors = []
            for i, c in enumerate(items):
                verdict = verdicts.get(f"{prefix}{i + 1}")
                if verdict == "supported":
                    c.verification = "verified"
                    survivors.append(c)
                elif verdict is None:
                    survivors.append(c)  # verifier skipped it: keep as quote-checked
                else:
                    log.info("Verifier rejected %s%d (%s)", prefix, i + 1, verdict)
            items[:] = survivors

    return kept_m[:max_mcq], kept_q[:max_qa]
