"""Slide renderer for narrated video overviews (Pillow — no browser needed).

Six layouts mirror the script's beat kinds: title, bullets, steps, definition, quote and
summary. Text auto-fits: each block tries a few font sizes and picks the largest that fits.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---- Design tokens -------------------------------------------------------------------------

BG_TOP = (10, 14, 30)
BG_BOTTOM = (22, 22, 56)
ACCENT = (129, 140, 248)  # indigo-400
ACCENT_2 = (45, 212, 191)  # teal-400
TEXT = (248, 250, 252)
TEXT_SOFT = (203, 213, 225)
MUTED = (148, 163, 184)

FONT_DIRS = [
    "/usr/share/fonts/opentype/inter",
    "/usr/share/fonts/truetype/inter",
    "/usr/local/share/fonts/inter",
]
DEJAVU = {
    "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
}
WEIGHTS = {
    "regular": "Regular",
    "medium": "Medium",
    "semibold": "SemiBold",
    "bold": "Bold",
    "extrabold": "ExtraBold",
    "italic": "Italic",
    "mediumitalic": "MediumItalic",
}


@lru_cache(maxsize=32)
def _find_inter(name: str) -> str | None:
    for directory in FONT_DIRS:
        for ext in ("otf", "ttf"):
            path = Path(directory) / f"Inter-{name}.{ext}"
            if path.exists():
                return str(path)
    for root in ("/usr/share/fonts", "/usr/local/share/fonts"):
        hits = sorted(Path(root).rglob(f"Inter-{name}.*")) if Path(root).exists() else []
        if hits:
            return str(hits[0])
    return None


@lru_cache(maxsize=128)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    name = WEIGHTS.get(weight, "Regular")
    inter = _find_inter(name)
    if inter:
        return ImageFont.truetype(inter, size)
    if "italic" in weight:
        fallback = DEJAVU["italic"]
    elif weight in ("semibold", "bold", "extrabold"):
        fallback = DEJAVU["bold"]
    else:
        fallback = DEJAVU["regular"]
    if Path(fallback).exists():
        return ImageFont.truetype(fallback, size)
    return ImageFont.load_default(size)


# ---- Text helpers ---------------------------------------------------------------------------


def wrap(text: str, fnt, max_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if fnt.getlength(trial) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        while fnt.getlength(word) > max_width and len(word) > 1:  # hard-split very long tokens
            cut = len(word)
            while cut > 1 and fnt.getlength(word[:cut]) > max_width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines


def fit(text: str, weight: str, sizes: list[int], max_width: float, max_lines: int, max_height: float | None = None):
    """Largest size whose wrapped text fits; the smallest size is truncated with an ellipsis."""
    for size in sizes:
        fnt = font(weight, size)
        lines = wrap(text, fnt, max_width)
        height = len(lines) * line_height(size)
        if len(lines) <= max_lines and (max_height is None or height <= max_height):
            return fnt, size, lines
    size = sizes[-1]
    fnt = font(weight, size)
    lines = wrap(text, fnt, max_width)[:max_lines]
    if lines:
        last = lines[-1]
        while last and fnt.getlength(last + "…") > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip(" ,;:") + "…"
    return fnt, size, lines


def line_height(size: int) -> int:
    return int(size * 1.28)


def draw_lines(draw: ImageDraw.ImageDraw, x: float, y: float, lines: list[str], fnt, size: int, fill) -> float:
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_height(size)
    return y


def draw_tracked(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, fnt, fill, tracking: float = 2.0) -> float:
    """Letter-spaced text (used for small uppercase eyebrows)."""
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += fnt.getlength(ch) + tracking
    return x


def truncate_to_width(text: str, fnt, max_width: float) -> str:
    if fnt.getlength(text) <= max_width:
        return text
    while text and fnt.getlength(text + "…") > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


# ---- Slide model ------------------------------------------------------------------------------


@dataclass
class SlideContext:
    index: int
    total: int
    topic_title: str
    unit_title: str
    doc_title: str
    source: str  # "p. 5" or ""


class SlideRenderer:
    def __init__(self, width: int = 1280, height: int = 720):
        self.w, self.h = width, height
        self.scale = width / 1280
        self.mx = int(96 * self.scale)
        self._background: Image.Image | None = None

    def s(self, v: float) -> int:
        return int(v * self.scale)

    def sizes(self, *values: int) -> list[int]:
        return [self.s(v) for v in values]

    # ---- background ------------------------------------------------------------------------
    def background(self) -> Image.Image:
        if self._background is None:
            w, h = self.w, self.h
            grad = Image.linear_gradient("L").resize((w, h))
            base = Image.composite(Image.new("RGB", (w, h), BG_BOTTOM), Image.new("RGB", (w, h), BG_TOP), grad)
            sw, sh = max(w // 8, 1), max(h // 8, 1)
            glow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            d = ImageDraw.Draw(glow)
            d.ellipse([sw * 0.60, -sh * 0.45, sw * 1.20, sh * 0.55], fill=ACCENT + (120,))
            d.ellipse([-sw * 0.25, sh * 0.65, sw * 0.30, sh * 1.35], fill=ACCENT_2 + (70,))
            glow = glow.filter(ImageFilter.GaussianBlur(sw * 0.09)).resize((w, h), Image.BICUBIC)
            self._background = Image.alpha_composite(base.convert("RGBA"), glow)
        return self._background.copy()

    # ---- chrome (header + footer) --------------------------------------------------------------
    def chrome(self, img: Image.Image, ctx: SlideContext) -> None:
        d = ImageDraw.Draw(img)
        top = self.s(44)
        # Brand mark
        box = self.s(28)
        mark = Image.new("RGBA", (box, box))
        mark_grad = Image.linear_gradient("L").rotate(90).resize((box, box))
        mark_img = Image.composite(Image.new("RGBA", (box, box), ACCENT_2 + (255,)), Image.new("RGBA", (box, box), ACCENT + (255,)), mark_grad)
        mask = Image.new("L", (box, box), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, box - 1, box - 1], radius=self.s(8), fill=255)
        mark.paste(mark_img, (0, 0), mask)
        img.alpha_composite(mark, (self.mx, top))
        d.text((self.mx + box + self.s(12), top + self.s(3)), "StudyForge", font=font("semibold", self.s(20)), fill=TEXT_SOFT)
        # Scene counter
        counter = f"{ctx.index + 1} / {ctx.total}"
        f = font("medium", self.s(19))
        d.text((self.w - self.mx - f.getlength(counter), top + self.s(4)), counter, font=f, fill=MUTED)
        # Footer: source + progress
        if ctx.source:
            d.text((self.mx, self.h - self.s(78)), f"Source · {ctx.source}", font=font("medium", self.s(18)), fill=MUTED)
        track_y = self.h - self.s(42)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle([self.mx, track_y, self.w - self.mx, track_y + self.s(5)], radius=self.s(3), fill=(255, 255, 255, 28))
        fill_to = self.mx + (self.w - 2 * self.mx) * (ctx.index + 1) / ctx.total
        od.rounded_rectangle([self.mx, track_y, fill_to, track_y + self.s(5)], radius=self.s(3), fill=ACCENT + (255,))
        img.alpha_composite(overlay)

    def eyebrow(self, d: ImageDraw.ImageDraw, y: float, text: str, color=ACCENT) -> float:
        f = font("semibold", self.s(17))
        text = truncate_to_width(text.upper(), f, (self.w - 2 * self.mx) * 0.8)
        draw_tracked(d, self.mx, y, text, f, color, tracking=self.s(2.2))
        return y + self.s(40)

    def heading(self, d: ImageDraw.ImageDraw, y: float, text: str) -> float:
        fnt, size, lines = fit(text, "bold", self.sizes(54, 48, 42, 38), self.w - 2 * self.mx, 2)
        return draw_lines(d, self.mx, y, lines, fnt, size, TEXT) + self.s(30)

    # ---- layouts --------------------------------------------------------------------------------
    def render(self, beat: dict, ctx: SlideContext) -> Image.Image:
        img = self.background()
        kind = beat.get("kind", "bullets")
        points = [p for p in beat.get("points", []) if p]
        if kind == "title":
            self._title(img, beat, ctx)
        elif kind == "definition" and (beat.get("term") or beat.get("definition")):
            self._definition(img, beat, ctx)
        elif kind == "quote" and beat.get("quote"):
            self._quote(img, beat, ctx)
        elif kind == "steps" and points:
            self._steps(img, beat, ctx, points)
        elif kind == "summary" and points:
            self._summary(img, beat, ctx, points)
        elif points:
            self._bullets(img, beat, ctx, points)
        else:
            self._paragraph(img, beat, ctx)
        self.chrome(img, ctx)
        return img.convert("RGB")

    def _title(self, img: Image.Image, beat: dict, ctx: SlideContext) -> None:
        d = ImageDraw.Draw(img)
        width = self.w - 2 * self.mx
        tf, tsize, tlines = fit(beat.get("heading") or ctx.topic_title, "bold", self.sizes(76, 68, 60, 54, 48), width * 0.92, 3)
        sub = f"Video overview · {ctx.doc_title}" if ctx.doc_title else "Video overview"
        sf = font("medium", self.s(24))
        block = self.s(40) + len(tlines) * line_height(tsize) + self.s(34) + self.s(6) + self.s(30) + self.s(30)
        y = (self.h - block) / 2 - self.s(10)
        y = self.eyebrow(d, y, ctx.unit_title or "Topic")
        y = draw_lines(d, self.mx, y, tlines, tf, tsize, TEXT) + self.s(22)
        bar = Image.linear_gradient("L").rotate(90).resize((self.s(140), self.s(6)))
        bar_img = Image.composite(Image.new("RGBA", bar.size, ACCENT_2 + (255,)), Image.new("RGBA", bar.size, ACCENT + (255,)), bar)
        img.alpha_composite(bar_img, (self.mx, int(y)))
        y += self.s(34)
        d.text((self.mx, y), truncate_to_width(sub, sf, width), font=sf, fill=MUTED)

    def _bullets(self, img: Image.Image, beat: dict, ctx: SlideContext, points: list[str]) -> None:
        d = ImageDraw.Draw(img)
        y = self.eyebrow(d, self.s(128), ctx.topic_title)
        y = self.heading(d, y, beat.get("heading") or ctx.topic_title)
        text_x = self.mx + self.s(40)
        width = self.w - self.mx - text_x
        available = self.h - self.s(110) - y
        for sizes in (self.sizes(34, 32), self.sizes(30, 28), self.sizes(26, 24)):
            blocks = [fit(p, "regular", sizes, width, 3) for p in points]
            total = sum(len(b[2]) * line_height(b[1]) for b in blocks) + self.s(24) * (len(blocks) - 1)
            if total <= available:
                break
        for fnt, size, lines in blocks:
            cy = y + line_height(size) / 2 - self.s(2)
            r = self.s(7)
            d.ellipse([self.mx + self.s(6) - r, cy - r, self.mx + self.s(6) + r, cy + r], fill=ACCENT)
            y = draw_lines(d, text_x, y, lines, fnt, size, TEXT_SOFT) + self.s(24)

    def _steps(self, img: Image.Image, beat: dict, ctx: SlideContext, points: list[str]) -> None:
        d = ImageDraw.Draw(img)
        y = self.eyebrow(d, self.s(128), ctx.topic_title)
        y = self.heading(d, y, beat.get("heading") or "Step by step")
        dia = self.s(46)
        text_x = self.mx + dia + self.s(26)
        width = self.w - self.mx - text_x
        blocks = [fit(p, "medium", self.sizes(31, 28, 25), width, 2) for p in points]
        centers = []
        for i, (fnt, size, lines) in enumerate(blocks):
            block_h = max(dia, len(lines) * line_height(size))
            cy = y + block_h / 2
            centers.append(cy)
            text_y = cy - len(lines) * line_height(size) / 2
            draw_lines(d, text_x, text_y, lines, fnt, size, TEXT_SOFT)
            y += block_h + self.s(22)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for a, b in zip(centers, centers[1:]):
            od.line([(self.mx + dia / 2, a + dia / 2 + self.s(4)), (self.mx + dia / 2, b - dia / 2 - self.s(4))], fill=(255, 255, 255, 45), width=self.s(2))
        img.alpha_composite(overlay)
        nf = font("bold", self.s(21))
        for i, cy in enumerate(centers):
            d.ellipse([self.mx, cy - dia / 2, self.mx + dia, cy + dia / 2], fill=ACCENT)
            label = str(i + 1)
            d.text((self.mx + dia / 2, cy), label, font=nf, fill=(15, 18, 40), anchor="mm")

    def _definition(self, img: Image.Image, beat: dict, ctx: SlideContext) -> None:
        d = ImageDraw.Draw(img)
        y = self.eyebrow(d, self.s(140), "Key term")
        term = beat.get("term") or beat.get("heading") or ctx.topic_title
        width = self.w - 2 * self.mx
        tf, tsize, tlines = fit(term, "bold", self.sizes(64, 56, 48, 42), width, 2)
        y = draw_lines(d, self.mx, y, tlines, tf, tsize, TEXT) + self.s(28)
        pad = self.s(40)
        definition = beat.get("definition") or beat.get("narration", "")
        max_h = self.h - self.s(120) - y - 2 * pad
        df, dsize, dlines = fit(definition, "regular", self.sizes(34, 31, 28, 25), width - 2 * pad - self.s(10), 6, max_h)
        card_h = len(dlines) * line_height(dsize) + 2 * pad
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle([self.mx, y, self.w - self.mx, y + card_h], radius=self.s(22), fill=(255, 255, 255, 14), outline=(255, 255, 255, 36), width=self.s(2))
        od.rounded_rectangle([self.mx + self.s(18), y + pad, self.mx + self.s(24), y + card_h - pad], radius=self.s(3), fill=ACCENT_2 + (255,))
        img.alpha_composite(overlay)
        draw_lines(d, self.mx + pad + self.s(10), y + pad, dlines, df, dsize, TEXT_SOFT)

    def _quote(self, img: Image.Image, beat: dict, ctx: SlideContext) -> None:
        d = ImageDraw.Draw(img)
        width = self.w - 2 * self.mx - self.s(40)
        qf, qsize, qlines = fit(beat["quote"], "mediumitalic", self.sizes(42, 38, 34, 31, 28), width, 6)
        cite = "— From your notes"
        cf = font("medium", self.s(22))
        block = len(qlines) * line_height(qsize) + self.s(36) + self.s(30)
        y = max(self.s(150), (self.h - block) / 2)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.text((self.mx - self.s(10), y - self.s(120)), "“", font=font("extrabold", self.s(200)), fill=ACCENT + (95,))
        img.alpha_composite(overlay)
        if beat.get("heading"):
            self.eyebrow(d, self.s(128), beat["heading"])
        y = draw_lines(d, self.mx + self.s(20), y, qlines, qf, qsize, TEXT) + self.s(36)
        d.text((self.mx + self.s(20), y), cite, font=cf, fill=ACCENT)

    def _summary(self, img: Image.Image, beat: dict, ctx: SlideContext, points: list[str]) -> None:
        d = ImageDraw.Draw(img)
        y = self.eyebrow(d, self.s(128), ctx.topic_title)
        y = self.heading(d, y, beat.get("heading") or "Key takeaways")
        pad = self.s(24)
        icon = self.s(34)
        text_x = self.mx + pad + icon + self.s(20)
        width = self.w - self.mx - pad - text_x
        blocks = [fit(p, "medium", self.sizes(29, 26, 24), width, 2) for p in points[:4]]
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        positions = []
        for fnt, size, lines in blocks:
            card_h = max(icon, len(lines) * line_height(size)) + 2 * pad - self.s(6)
            od.rounded_rectangle([self.mx, y, self.w - self.mx, y + card_h], radius=self.s(18), fill=(255, 255, 255, 12), outline=(255, 255, 255, 26), width=self.s(1) or 1)
            positions.append((y, card_h, fnt, size, lines))
            y += card_h + self.s(16)
        img.alpha_composite(overlay)
        for top, card_h, fnt, size, lines in positions:
            cy = top + card_h / 2
            ix = self.mx + pad
            d.ellipse([ix, cy - icon / 2, ix + icon, cy + icon / 2], fill=ACCENT_2)
            d.line(
                [(ix + icon * 0.28, cy + icon * 0.02), (ix + icon * 0.44, cy + icon * 0.18), (ix + icon * 0.74, cy - icon * 0.16)],
                fill=(10, 30, 35), width=max(self.s(4), 2), joint="curve",
            )
            draw_lines(d, text_x, cy - len(lines) * line_height(size) / 2, lines, fnt, size, TEXT_SOFT)

    def _paragraph(self, img: Image.Image, beat: dict, ctx: SlideContext) -> None:
        d = ImageDraw.Draw(img)
        y = self.eyebrow(d, self.s(128), ctx.topic_title)
        y = self.heading(d, y, beat.get("heading") or ctx.topic_title)
        pf, psize, plines = fit(beat.get("narration", ""), "regular", self.sizes(32, 29, 26), self.w - 2 * self.mx, 7, self.h - self.s(120) - y)
        draw_lines(d, self.mx, y, plines, pf, psize, TEXT_SOFT)
