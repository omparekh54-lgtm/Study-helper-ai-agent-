"""Exercise the real Gemini/Groq SDK code paths against a mocked HTTP layer."""

import asyncio
import json
import time

import httpx
import pytest

from app.services.llm.base import LLMError, RateLimiter, extract_json, retry_delay_from_text
from app.services.llm.gemini import GeminiGenerator
from app.services.llm.groq_client import GroqGenerator
from app.services.llm.schemas import Outline, VerificationResult

OUTLINE = {
    "document_title": "Photosynthesis",
    "overview": "Covers the light reactions.",
    "units": [{"title": "Unit 1", "topics": [{"title": "Light reactions", "summary": "S", "key_points": ["k"], "chunk_ids": [1]}]}],
}


def gemini_ok(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"role": "model", "parts": [{"text": json.dumps(payload)}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10, "totalTokenCount": 20},
        },
    )


def gemini_error(code: int, status: str, message: str) -> httpx.Response:
    return httpx.Response(code, json={"error": {"code": code, "status": status, "message": message}})


def make_gemini(handler, models=("gemini-a", "gemini-b")) -> tuple[GeminiGenerator, list[str]]:
    calls: list[str] = []

    def route(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "GET" and request.url.path.endswith("/models"):
            return httpx.Response(200, json={"models": [{"name": f"models/{m}"} for m in models]})
        return handler(request, len(calls))

    client = httpx.AsyncClient(transport=httpx.MockTransport(route))
    return GeminiGenerator("test-key", list(models), rpm=1000, http_client=client), calls


async def test_gemini_parses_structured_output():
    gen, calls = make_gemini(lambda req, n: gemini_ok(OUTLINE))
    result = await gen.generate_json(system="s", prompt="p", schema=Outline)
    assert result.units[0].topics[0].title == "Light reactions"
    assert any("gemini-a:generateContent" in c for c in calls)


async def test_gemini_sends_schema_and_key():
    seen = {}

    def handler(req: httpx.Request, n: int) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        seen["key"] = req.headers.get("x-goog-api-key")
        return gemini_ok(OUTLINE)

    gen, _ = make_gemini(handler)
    await gen.generate_json(system="be brief", prompt="p", schema=Outline)
    config = seen["body"]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert "responseSchema" in config or "responseJsonSchema" in config
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert seen["key"] == "test-key"


async def test_gemini_falls_back_when_model_missing():
    def handler(req, n):
        if "gemini-a" in req.url.path:
            return gemini_error(404, "NOT_FOUND", "models/gemini-a is not found")
        return gemini_ok(OUTLINE)

    gen, calls = make_gemini(handler)
    result = await gen.generate_json(system="s", prompt="p", schema=Outline)
    assert result.document_title == "Photosynthesis"
    assert gen.models == ["gemini-b"]


async def test_gemini_switches_model_on_daily_quota():
    def handler(req, n):
        if "gemini-a" in req.url.path:
            return gemini_error(429, "RESOURCE_EXHAUSTED", "Quota exceeded for GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        return gemini_ok(OUTLINE)

    gen, calls = make_gemini(handler)
    await gen.generate_json(system="s", prompt="p", schema=Outline)
    assert sum("gemini-a:generate" in c for c in calls) == 1
    # The exhausted model is parked, so the next request goes straight to the other one.
    await gen.generate_json(system="s", prompt="p", schema=Outline)
    assert sum("gemini-a:generate" in c for c in calls) == 1


async def test_gemini_bad_key_is_not_retried():
    gen, calls = make_gemini(lambda req, n: gemini_error(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key."))
    with pytest.raises(LLMError, match="API key"):
        await gen.generate_json(system="s", prompt="p", schema=Outline)
    assert sum(":generateContent" in c for c in calls) == 1


async def test_gemini_retries_bad_json_then_gives_up():
    gen, calls = make_gemini(lambda req, n: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}))
    with pytest.raises(LLMError):
        await gen.generate_json(system="s", prompt="p", schema=Outline)


def _model_of(req: httpx.Request) -> str:
    return req.url.path.rsplit("/", 1)[-1].split(":")[0]


async def test_gemini_rotates_parallel_calls_across_models():
    used: list[str] = []

    def handler(req, n):
        used.append(_model_of(req))
        return gemini_ok(OUTLINE)

    gen, _ = make_gemini(handler, models=("gemini-a", "gemini-b", "gemini-a-lite"))
    await asyncio.gather(*(gen.generate_json(system="s", prompt="p", schema=Outline) for _ in range(4)))
    # Full models share the load; the Lite model is only a fallback for normal calls.
    assert sorted(used) == ["gemini-a", "gemini-a", "gemini-b", "gemini-b"]


async def test_gemini_fast_calls_prefer_lite_models():
    used: list[str] = []

    def handler(req, n):
        used.append(_model_of(req))
        return gemini_ok(OUTLINE)

    gen, _ = make_gemini(handler, models=("gemini-a", "gemini-a-lite"))
    await gen.generate_json(system="s", prompt="p", schema=Outline, fast=True)
    assert used == ["gemini-a-lite"]


async def test_gemini_sends_low_thinking_and_drops_it_if_rejected():
    bodies: list[dict] = []

    def handler(req, n):
        body = json.loads(req.content)
        bodies.append(body)
        if "thinkingConfig" in body["generationConfig"]:
            return gemini_error(400, "INVALID_ARGUMENT", "Thinking level is not supported for this model.")
        return gemini_ok(OUTLINE)

    gen, _ = make_gemini(handler, models=("gemini-3-test",))
    result = await gen.generate_json(system="s", prompt="p", schema=Outline)
    assert result.document_title == "Photosynthesis"
    thinking = bodies[0]["generationConfig"]["thinkingConfig"]
    assert (thinking.get("thinkingLevel") or thinking.get("thinking_level")) == "LOW"
    assert "thinkingConfig" not in bodies[1]["generationConfig"]
    assert gen.models == ["gemini-3-test"]  # the model is kept, not dropped as "unsupported"


def groq_ok(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(payload)}}],
        },
    )


def make_groq(handler, models=("openai/gpt-oss-120b", "openai/gpt-oss-20b")):
    bodies: list[dict] = []

    def route(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        bodies.append(body)
        return handler(body, len(bodies))

    client = httpx.AsyncClient(transport=httpx.MockTransport(route))
    return GroqGenerator("gsk_test", list(models), rpm=1000, tpm=10**6, http_client=client), bodies


async def test_groq_verifier_round_trip():
    verdicts = {"results": [{"id": "m1", "verdict": "supported", "note": "ok"}]}
    gen, bodies = make_groq(lambda body, n: groq_ok(verdicts))
    result = await gen.generate_json(system="check", prompt="[m1] ...", schema=VerificationResult)
    assert result.results[0].verdict == "supported"
    assert bodies[0]["response_format"] == {"type": "json_object"}
    assert bodies[0]["reasoning_effort"] == "low"
    assert "JSON schema" in bodies[0]["messages"][0]["content"]


async def test_groq_drops_decommissioned_model():
    def handler(body, n):
        if body["model"] == "openai/gpt-oss-120b":
            return httpx.Response(400, json={"error": {"message": "The model has been decommissioned", "type": "invalid_request_error", "code": "model_decommissioned"}})
        return groq_ok({"results": []})

    gen, bodies = make_groq(handler)
    await gen.generate_json(system="s", prompt="p", schema=VerificationResult)
    assert gen.models == ["openai/gpt-oss-20b"]


async def test_groq_rate_limit_waits_then_succeeds():
    def handler(body, n):
        if n == 1:
            return httpx.Response(429, headers={"retry-after": "0.1"}, json={"error": {"message": "Rate limit reached for model (TPM). Please try again in 0.1s", "type": "tokens"}})
        return groq_ok({"results": []})

    gen, bodies = make_groq(handler)
    await gen.generate_json(system="s", prompt="p", schema=VerificationResult)
    assert len(bodies) == 2


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": [1, 2]} Hope that helps.') == {"a": [1, 2]}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_retry_delay_parsing():
    assert retry_delay_from_text("'retryDelay': '31s'", 5) == 32.0
    assert retry_delay_from_text("Please try again in 7.5s.", 5) == 8.5
    assert retry_delay_from_text("nothing", 5) == 5


async def test_rate_limiter_spaces_requests():
    limiter = RateLimiter(rpm=2, window=0.5)
    start = time.monotonic()
    await asyncio.gather(*(limiter.acquire() for _ in range(3)))
    assert time.monotonic() - start >= 0.45


async def test_rate_limiter_token_budget():
    limiter = RateLimiter(rpm=100, tpm=100, window=0.4)
    start = time.monotonic()
    await limiter.acquire(80)
    await limiter.acquire(80)  # must wait for the first to leave the window
    assert time.monotonic() - start >= 0.35
