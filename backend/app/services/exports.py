"""Printable PDF exports: a study pack (summaries + theory Q&A) and practice tests with an answer key."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

INDIGO = colors.HexColor("#4F46E5")
INK = colors.HexColor("#0F172A")
SOFT = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#E2E8F0")
GREEN = colors.HexColor("#059669")


def _register_fonts() -> tuple[str, str, str]:
    candidates = {
        "SF": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
        "SF-Bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
        "SF-Italic": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"],
    }
    try:
        for name, paths in candidates.items():
            path = next(p for p in paths if Path(p).exists())
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, path))
        pdfmetrics.registerFontFamily("SF", normal="SF", bold="SF-Bold", italic="SF-Italic", boldItalic="SF-Bold")
        return "SF", "SF-Bold", "SF-Italic"
    except (StopIteration, Exception):  # noqa: BLE001 — fall back to built-in fonts
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


REGULAR, BOLD, ITALIC = _register_fonts()

STYLES = {
    "title": ParagraphStyle("title", fontName=BOLD, fontSize=22, leading=28, textColor=INK, spaceAfter=4),
    "subtitle": ParagraphStyle("subtitle", fontName=REGULAR, fontSize=10.5, leading=15, textColor=MUTED, spaceAfter=14),
    "unit": ParagraphStyle("unit", fontName=BOLD, fontSize=9, leading=12, textColor=INDIGO, spaceBefore=6, spaceAfter=2),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=15, leading=20, textColor=INK, spaceBefore=4, spaceAfter=6),
    "body": ParagraphStyle("body", fontName=REGULAR, fontSize=10.5, leading=15.5, textColor=SOFT, alignment=TA_LEFT),
    "q": ParagraphStyle("q", fontName=BOLD, fontSize=11, leading=15.5, textColor=INK, spaceBefore=10, spaceAfter=4),
    "meta": ParagraphStyle("meta", fontName=ITALIC, fontSize=8.5, leading=12, textColor=MUTED, spaceBefore=3, spaceAfter=4),
    "option": ParagraphStyle("option", fontName=REGULAR, fontSize=10.5, leading=15, textColor=SOFT, leftIndent=14),
    "label": ParagraphStyle("label", fontName=BOLD, fontSize=9, leading=12, textColor=MUTED, spaceBefore=8, spaceAfter=2),
}


@dataclass
class QAExport:
    question: str
    answer: str
    kind: str
    source: str
    verification: str


@dataclass
class MCQExport:
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    source: str
    difficulty: str


@dataclass
class TopicExport:
    title: str
    unit: str
    summary: str
    key_points: list[str] = field(default_factory=list)
    qa: list[QAExport] = field(default_factory=list)
    mcqs: list[MCQExport] = field(default_factory=list)


def _inline(text: str) -> str:
    text = escape(text.strip())
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    return text


def markdown_flowables(md: str) -> list:
    """Tiny markdown subset (paragraphs, **bold**, *italic*, - bullets) → flowables."""
    out: list = []
    bullets: list[str] = []

    def flush_bullets() -> None:
        if bullets:
            out.append(
                ListFlowable(
                    [ListItem(Paragraph(_inline(b), STYLES["body"]), leftIndent=12) for b in bullets],
                    bulletType="bullet", start="•", leftIndent=10, bulletFontSize=9, bulletColor=INDIGO,
                )
            )
            bullets.clear()

    for block in re.split(r"\n\s*\n", md.strip()):
        for line in block.split("\n"):
            stripped = line.strip()
            m = re.match(r"^([-*•]|\d+[.)])\s+(.*)", stripped)
            if m:
                bullets.append(m.group(2))
            elif stripped:
                flush_bullets()
                out.append(Paragraph(_inline(stripped), STYLES["body"]))
        flush_bullets()
        out.append(Spacer(1, 4))
    return out


def _decorate(doc_title: str):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)
        canvas.setFont(BOLD, 8.5)
        canvas.setFillColor(INDIGO)
        canvas.drawString(18 * mm, h - 11.5 * mm, "StudyForge")
        canvas.setFont(REGULAR, 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(w - 18 * mm, h - 11.5 * mm, doc_title[:90])
        canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    return draw


def _build(flowables: list, doc_title: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=22 * mm, bottomMargin=18 * mm,
        title=doc_title, author="StudyForge",
    )
    deco = _decorate(doc_title)
    doc.build(flowables, onFirstPage=deco, onLaterPages=deco)
    return buf.getvalue()


def _source_line(source: str, verification: str) -> str:
    badge = "Verified against your notes" if verification == "verified" else "Quote checked against your notes"
    return f"Source: {escape(source)} · {badge}" if source else badge


def study_pack_pdf(doc_title: str, overview: str, topics: list[TopicExport]) -> bytes:
    story: list = [
        Paragraph(escape(doc_title), STYLES["title"]),
        Paragraph(f"Study pack · {len(topics)} topics · generated {date.today():%d %b %Y}", STYLES["subtitle"]),
    ]
    if overview:
        story += [Paragraph(escape(overview), STYLES["body"]), Spacer(1, 10)]

    for i, t in enumerate(topics):
        if i:
            story.append(CondPageBreak(90 * mm))
            story.append(Spacer(1, 10))
        story += [Paragraph(escape(t.unit.upper()), STYLES["unit"]), Paragraph(escape(t.title), STYLES["h2"])]
        if t.summary:
            story.append(Paragraph(escape(t.summary), STYLES["body"]))
        if t.key_points:
            story.append(Paragraph("KEY POINTS", STYLES["label"]))
            story += markdown_flowables("\n".join(f"- {k}" for k in t.key_points))
        if t.qa:
            story.append(Paragraph("EXAM QUESTIONS", STYLES["label"]))
        for n, qa in enumerate(t.qa, start=1):
            block = [Paragraph(f"Q{n}. {_inline(qa.question)}", STYLES["q"]), *markdown_flowables(qa.answer)]
            block.append(Paragraph(_source_line(qa.source, qa.verification), STYLES["meta"]))
            story.append(KeepTogether(block) if len(qa.answer) < 900 else block[0])
            if len(qa.answer) >= 900:
                story += block[1:]
    return _build(story, doc_title)


def quiz_pdf(doc_title: str, heading: str, questions: list[MCQExport]) -> bytes:
    letters = "ABCD"
    story: list = [
        Paragraph(escape(heading), STYLES["title"]),
        Paragraph(f"Practice test · {len(questions)} questions · {escape(doc_title)}", STYLES["subtitle"]),
        Paragraph("Choose the single best answer. The answer key with explanations is at the end.", STYLES["body"]),
        Spacer(1, 6),
    ]
    for n, q in enumerate(questions, start=1):
        block = [Paragraph(f"{n}. {_inline(q.question)}", STYLES["q"])]
        block += [Paragraph(f"<b>{letters[i]}.</b>  {_inline(o)}", STYLES["option"]) for i, o in enumerate(q.options)]
        story.append(KeepTogether(block))

    story += [PageBreak(), Paragraph("Answer key", STYLES["title"]), Spacer(1, 8)]
    for n, q in enumerate(questions, start=1):
        story.append(
            KeepTogether(
                [
                    Paragraph(
                        f"{n}. <font color='#059669'><b>{letters[q.answer_index]}</b></font> — {_inline(q.options[q.answer_index])}",
                        STYLES["q"],
                    ),
                    Paragraph(_inline(q.explanation), STYLES["body"]),
                    Paragraph(f"Source: {escape(q.source)}" if q.source else "", STYLES["meta"]),
                ]
            )
        )
    return _build(story, doc_title)
