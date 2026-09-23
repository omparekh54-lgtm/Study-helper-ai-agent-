import pytest

from app.services.llm import LLMError
from app.services.llm.schemas import MCQ, QA, VerificationResult, Verdict
from app.services.verify import SourceChunk, evidence_window, locate_quote, normalize, shuffle_options, verify_kit

CHUNKS = {
    1: SourceChunk(1, "Photosynthesis takes place in chloroplasts, which are found mainly in the mesophyll cells of leaves.", "p. 1"),
    2: SourceChunk(2, "To replace the electrons lost from photosystem II, water molecules are split in a process called photolysis. "
                      "Photolysis releases oxygen as a by-product.", "p. 2"),
}


def mcq(question="Where does photosynthesis take place?", quote="takes place in chloroplasts, which are found mainly", chunk_id=1, **kw):
    base = dict(
        question=question,
        options=["Chloroplasts", "Mitochondria", "Ribosomes", "Nucleus"],
        answer_index=0,
        explanation="Notes say chloroplasts.",
        difficulty="easy",
        source_quote=quote,
        chunk_id=chunk_id,
    )
    base.update(kw)
    return MCQ(**base)


def qa(quote="water molecules are split in a process called photolysis", chunk_id=2):
    return QA(question="What is photolysis?", answer="Photolysis is the splitting of water using light energy, releasing oxygen.",
              kind="short", source_quote=quote, chunk_id=chunk_id)


def test_normalize_handles_typography():
    assert normalize("“RuBisCO’s” role—fixing CO₂!") == normalize('"rubisco\'s" role-fixing co2!')


def test_locate_quote_exact_fuzzy_and_missing():
    assert locate_quote("water molecules are split", CHUNKS, preferred=1).idx == 2  # found in another chunk
    assert locate_quote("water molecule are split in a process called photolysis", CHUNKS).idx == 2  # small typo tolerated
    assert locate_quote("mitochondria produce glucose from sunlight directly", CHUNKS) is None
    assert locate_quote("too short", CHUNKS) is None


def test_shuffle_preserves_correct_answer():
    original = mcq()
    shuffled = shuffle_options(original)
    assert sorted(shuffled.options) == sorted(original.options)
    assert shuffled.options[shuffled.answer_index] == "Chloroplasts"
    assert shuffle_options(original) == shuffled  # deterministic


def test_evidence_window_centres_on_quote():
    text = "x " * 400 + "The Calvin cycle takes place in the stroma." + " y" * 400
    window = evidence_window(text, "Calvin cycle takes place in the stroma", 200)
    assert "Calvin cycle" in window and window.startswith("…")


class StubVerifier:
    name = "stub"

    def __init__(self, verdicts=None, fail=False):
        self.verdicts, self.fail, self.calls = verdicts or {}, fail, 0

    async def generate_json(self, *, system, prompt, schema, max_output_tokens=0):
        self.calls += 1
        if self.fail:
            raise LLMError("quota")
        import re

        ids = re.findall(r"^\[(\w+)\]", prompt, re.MULTILINE)
        return VerificationResult(results=[Verdict(id=i, verdict=self.verdicts.get(i, "supported"), note="") for i in ids])


async def test_verify_kit_drops_ungrounded_and_rejected_items():
    items = [
        mcq(),
        mcq(question="Q2?", quote="this quote is not in the document at all anywhere"),  # fails grounding
        mcq(question="Q3?", options=["A", "B", "All of the above", "D"]),  # banned option
        mcq(question="Q4?", quote="Photolysis releases oxygen as a by-product", chunk_id=2),
    ]
    verifier = StubVerifier({"m2": "ambiguous"})  # after grounding, Q4 is m2
    kept_m, kept_q = await verify_kit(items, [qa()], CHUNKS, verifier)
    assert [c.item.question for c in kept_m] == ["Where does photosynthesis take place?"]
    assert kept_m[0].verification == "verified"
    assert kept_m[0].chunk.loc == "p. 1"
    assert kept_q[0].verification == "verified"
    assert verifier.calls == 2


async def test_verifier_outage_degrades_to_quote_checked():
    kept_m, kept_q = await verify_kit([mcq()], [qa()], CHUNKS, StubVerifier(fail=True))
    assert kept_m[0].verification == "quote_checked"
    assert kept_q[0].verification == "quote_checked"


async def test_no_verifier_configured():
    kept_m, _ = await verify_kit([mcq()], [], CHUNKS, None)
    assert kept_m[0].verification == "quote_checked"


@pytest.mark.parametrize("bad", [
    {"options": ["A", "B", "C"]},
    {"options": ["A", "A", "C", "D"]},
    {"answer_index": 4},
])
async def test_structural_checks(bad):
    kept_m, _ = await verify_kit([mcq(**bad)], [], CHUNKS, None)
    assert kept_m == []
