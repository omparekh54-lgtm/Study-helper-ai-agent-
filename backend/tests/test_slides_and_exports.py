from app.services.exports import MCQExport, QAExport, TopicExport, markdown_flowables, quiz_pdf, study_pack_pdf
from app.services.study import normalize_outline, sanitize_beats, ChunkRef
from app.services.llm.schemas import Beat, Outline, OutlineTopic, OutlineUnit
from app.services.video.slides import SlideContext, SlideRenderer

CTX = SlideContext(index=1, total=4, topic_title="Calvin cycle", unit_title="Unit 2", doc_title="Bio", source="p. 3")


def beat(kind, **kw):
    base = dict(kind=kind, heading="Heading", points=[], quote="", term="", definition="", narration="Narration text here.", chunk_id=0)
    base.update(kw)
    return base


def test_every_layout_renders_at_full_size():
    r = SlideRenderer()
    long = "An extremely long sentence that keeps going and going " * 12
    for b in [
        beat("title"),
        beat("bullets", points=["one", long, "three"]),
        beat("steps", points=["a", "b", "c", "d"]),
        beat("definition", term="RuBisCO", definition=long),
        beat("quote", quote=long),
        beat("summary", points=["x", "y", long]),
        beat("bullets"),  # no points → falls back to paragraph layout
        beat("quote"),  # no quote → falls back
    ]:
        img = r.render(b, CTX)
        assert img.size == (1280, 720)


def test_renderer_scales_to_other_resolutions():
    assert SlideRenderer(1920, 1080).render(beat("summary", points=["a"]), CTX).size == (1920, 1080)


def test_sanitize_beats_ensures_title_first():
    beats = [Beat(**beat("bullets", points=["p"]))]
    cleaned = sanitize_beats(beats, "Calvin cycle")
    assert cleaned[0].kind == "title" and cleaned[0].heading == "Calvin cycle"


def test_normalize_outline_repairs_references():
    chunks = [ChunkRef(i, i, i, "x" * 300, f"p. {i}") for i in range(1, 6)]
    outline = Outline(
        document_title="Doc",
        overview="o",
        units=[
            OutlineUnit(title="U2", topics=[OutlineTopic(title="Later", summary="", key_points=[], chunk_ids=[4])]),
            OutlineUnit(title="U1", topics=[
                OutlineTopic(title="Early", summary="", key_points=[], chunk_ids=[1, 99]),
                OutlineTopic(title="early", summary="", key_points=[], chunk_ids=[2]),  # duplicate title
                OutlineTopic(title="Empty", summary="", key_points=[], chunk_ids=[42]),  # invalid refs
            ]),
        ],
    )
    title, _, topics = normalize_outline(outline, chunks)
    assert [t.title for t in topics] == ["Early", "Later"]  # document order, dupes/empties dropped
    assert topics[0].unit_idx == 0 and topics[0].unit_title == "U1"
    covered = {c for t in topics for c in t.chunk_idxs}
    assert covered == {1, 2, 3, 4, 5}  # orphan chunks attached to nearest topic


def test_markdown_subset():
    flow = markdown_flowables("Intro with **bold** & <angle>.\n\n- first\n- second\n\nOutro")
    assert len(flow) >= 3


def test_pdfs_render_unicode():
    topic = TopicExport(
        title="Équations & CO₂", unit="Unit 1", summary="Δ energy ≥ 0 → products",
        key_points=["α-helix", "β-sheet"],
        qa=[QAExport("Why?", "Because **ATP** is used.\n\n- step one\n- step two", "long", "p. 2", "verified")],
    )
    assert study_pack_pdf("Doc", "Overview", [topic]).startswith(b"%PDF")
    mcq = MCQExport("Which?", ["A", "B", "C", "D"], 2, "C is right.", "p. 1", "easy")
    assert quiz_pdf("Doc", "Topic", [mcq] * 12).startswith(b"%PDF")
