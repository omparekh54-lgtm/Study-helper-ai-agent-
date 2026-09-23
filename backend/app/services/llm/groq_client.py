"""Groq client used as an independent verifier (a different model family than the generator)."""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncGroq,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)

from app.services.llm.base import (
    LLMError,
    LLMNotConfigured,
    RateLimiter,
    T,
    estimate_tokens,
    parse_model,
    retry_delay_from_text,
)

log = logging.getLogger(__name__)


class GroqGenerator:
    name = "groq"

    def __init__(
        self,
        api_key: str,
        models: list[str],
        rpm: int = 25,
        tpm: int = 7000,
        http_client: httpx.AsyncClient | None = None,
    ):
        if not api_key:
            raise LLMNotConfigured("GROQ_API_KEY is not set")
        self.client = AsyncGroq(api_key=api_key, max_retries=0, timeout=90.0, http_client=http_client)
        self.models = list(models)
        self.limiter = RateLimiter(rpm, tpm)
        self._cooldown: dict[str, float] = {}

    def _candidates(self) -> list[str]:
        now = time.monotonic()
        ready = [m for m in self.models if self._cooldown.get(m, 0) <= now]
        return ready or sorted(self.models, key=lambda m: self._cooldown.get(m, 0))

    async def generate_json(self, *, system: str, prompt: str, schema: type[T], max_output_tokens: int = 2048) -> T:
        schema_hint = json.dumps(schema.model_json_schema(), separators=(",", ":"))
        system_full = f"{system}\n\nRespond with a single JSON object matching this JSON schema:\n{schema_hint}"
        budget = estimate_tokens(system_full, prompt) + max_output_tokens
        last_error: Exception | None = None

        for model in self._candidates():
            for attempt in range(4):
                await self.limiter.acquire(budget)
                kwargs: dict = {}
                if model.startswith("openai/gpt-oss"):
                    kwargs["reasoning_effort"] = "low"
                try:
                    completion = await self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_full},
                            {"role": "user", "content": prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_completion_tokens=max_output_tokens,
                        **kwargs,
                    )
                    text = completion.choices[0].message.content or ""
                    return parse_model(text, schema)

                except AuthenticationError as exc:
                    raise LLMError("Groq rejected the API key — check GROQ_API_KEY.") from exc
                except RateLimitError as exc:
                    last_error = exc
                    msg = str(exc)
                    headers = exc.response.headers if exc.response is not None else {}
                    delay = float(headers.get("retry-after", 0) or 0) or retry_delay_from_text(msg, 15)
                    if "per day" in msg.lower() or "(tpd)" in msg.lower() or "(rpd)" in msg.lower() or delay > 60:
                        self._cooldown[model] = time.monotonic() + max(delay, 600)
                        log.warning("Groq %s daily limit reached; switching model", model)
                        break
                    await asyncio.sleep(min(delay, 60))
                    continue
                except (NotFoundError, BadRequestError) as exc:
                    last_error = exc
                    msg = str(exc).lower()
                    if "decommissioned" in msg or "does not exist" in msg or "not found" in msg or isinstance(exc, NotFoundError):
                        log.warning("Groq model %s unavailable, dropping it", model)
                        self.models = [m for m in self.models if m != model] or self.models
                        break
                    if "reasoning_effort" in msg and kwargs:
                        kwargs.clear()
                        continue
                    if "json" in msg and attempt < 1:  # json_validate_failed — try once more
                        continue
                    break
                except APIStatusError as exc:
                    last_error = exc
                    if exc.status_code >= 500:
                        await asyncio.sleep(min(2 ** attempt * 2, 20))
                        continue
                    break
                except (APIConnectionError, APITimeoutError, httpx.HTTPError) as exc:
                    last_error = exc
                    await asyncio.sleep(min(2 ** attempt * 2, 20))
                    continue
                except ValueError as exc:
                    last_error = exc
                    if attempt >= 1:
                        break
                    continue

        raise LLMError(f"Groq could not complete the request: {last_error}")
