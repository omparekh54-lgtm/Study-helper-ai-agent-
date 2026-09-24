"""Gemini client with model discovery, free-tier-aware rate limiting and model fallback."""

from __future__ import annotations

import asyncio
import itertools
import logging
import time

import httpx
from google import genai
from google.genai import errors, types

from app.services.llm.base import LLMError, LLMNotConfigured, RateLimiter, T, parse_model, retry_delay_from_text

log = logging.getLogger(__name__)


class GeminiGenerator:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        models: list[str],
        rpm: int = 5,
        http_client: httpx.AsyncClient | None = None,
        thinking_level: str = "low",
    ):
        if not api_key:
            raise LLMNotConfigured("GEMINI_API_KEY is not set")
        http_options = types.HttpOptions(timeout=180_000)
        if http_client is not None:
            http_options = types.HttpOptions(timeout=180_000, httpx_async_client=http_client)
        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.models = list(models)
        # Free-tier quotas are per model, so each model gets its own requests-per-minute budget.
        self._rpm = rpm
        self._limiters: dict[str, RateLimiter] = {}
        self._rr = itertools.count()
        # Gemini 3 models "think" at a high level by default, which is slow; study kits don't need it.
        self._thinking = (thinking_level or "").strip().upper()
        self._no_thinking: set[str] = set()  # models that rejected the thinking setting
        self._discovered = False
        self._discover_lock = asyncio.Lock()
        self._cooldown: dict[str, float] = {}  # model -> monotonic time when it may be used again

    async def _discover(self) -> None:
        """Keep only the preferred models this API key can actually use."""
        async with self._discover_lock:
            if self._discovered:
                return
            self._discovered = True
            try:
                available: set[str] = set()
                pager = await self.client.aio.models.list()
                async for m in pager:
                    if m.name:
                        available.add(m.name.removeprefix("models/"))
                usable = [m for m in self.models if m in available]
                if usable:
                    self.models = usable
                log.info("Gemini models in use: %s", self.models)
            except Exception as exc:  # noqa: BLE001 - discovery is best-effort
                log.warning("Gemini model discovery failed (%s); using configured list", exc)

    def _limiter(self, model: str) -> RateLimiter:
        if model not in self._limiters:
            self._limiters[model] = RateLimiter(self._rpm)
        return self._limiters[model]

    def _candidates(self, fast: bool = False) -> list[str]:
        """Order to try models in.

        Normal calls rotate between the full "Flash" models so parallel topics spread across
        separate free-tier buckets; Flash-Lite models are the fallback. `fast` calls (the outline)
        start with Flash-Lite, which is much quicker and has a far larger daily quota.
        """
        now = time.monotonic()
        ready = [m for m in self.models if self._cooldown.get(m, 0) <= now]
        if not ready:
            return sorted(self.models, key=lambda m: self._cooldown.get(m, 0))
        primary = [m for m in ready if "lite" not in m]
        lite = [m for m in ready if "lite" in m]
        if fast:
            return lite + primary
        if primary:
            k = next(self._rr) % len(primary)
            primary = primary[k:] + primary[:k]
        return primary + lite

    def _thinking_config(self, model: str) -> types.ThinkingConfig | None:
        if not self._thinking or model in self._no_thinking or not model.startswith("gemini-3"):
            return None
        return types.ThinkingConfig(thinking_level=self._thinking)

    async def generate_json(
        self, *, system: str, prompt: str, schema: type[T], max_output_tokens: int = 8192, fast: bool = False
    ) -> T:
        await self._discover()
        last_error: Exception | None = None

        for model in self._candidates(fast):
            for attempt in range(4):
                await self._limiter(model).acquire()
                try:
                    response = await self.client.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system,
                            response_mime_type="application/json",
                            response_schema=schema,
                            max_output_tokens=max_output_tokens,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                            thinking_config=self._thinking_config(model),
                        ),
                    )
                    text = response.text or ""
                    if not text.strip():
                        reason = ""
                        if response.candidates:
                            reason = str(response.candidates[0].finish_reason or "")
                        raise ValueError(f"empty response {reason}".strip())
                    return parse_model(text, schema)

                except errors.APIError as exc:
                    last_error = exc
                    msg = f"{exc.status or ''} {exc.message or ''} {exc}"
                    code = exc.code or 0
                    if code in (401, 403) or (code == 400 and "api key" in msg.lower()):
                        raise LLMError("Gemini rejected the API key — check GEMINI_API_KEY.") from exc
                    if code == 400 and "thinking" in msg.lower() and model not in self._no_thinking:
                        log.warning("Gemini %s doesn't accept the thinking setting; retrying without it", model)
                        self._no_thinking.add(model)
                        continue
                    if code == 404 or (code == 400 and ("not found" in msg.lower() or "not supported" in msg.lower())):
                        log.warning("Gemini model %s unavailable, dropping it: %s", model, exc.message)
                        self.models = [m for m in self.models if m != model] or self.models
                        break
                    if code == 429:
                        daily = "perday" in msg.replace(" ", "").lower() or "per day" in msg.lower()
                        if daily or attempt >= 1:
                            # Park this model and move to the next one (separate free-tier bucket).
                            self._cooldown[model] = time.monotonic() + (3600 if daily else 90)
                            log.warning("Gemini %s rate-limited (%s); switching model", model, "daily" if daily else "rpm")
                            break
                        delay = retry_delay_from_text(msg, 20)
                        log.info("Gemini %s rate-limited; retrying in %.0fs", model, delay)
                        await asyncio.sleep(delay)
                        continue
                    if code >= 500:
                        log.warning("Gemini %s server error %s (attempt %d): %s", model, code, attempt + 1, exc.message)
                        if attempt >= 1:
                            break  # overloaded model: move on instead of stalling the pipeline
                        await asyncio.sleep(min(2 ** attempt * 3, 30))
                        continue
                    log.warning("Gemini %s error %s: %s", model, code, exc.message)
                    break  # other 4xx: try the next model

                except ValueError as exc:  # malformed / truncated JSON
                    last_error = exc
                    log.warning("Gemini %s returned unusable output (attempt %d): %s", model, attempt + 1, exc)
                    if attempt >= 1:
                        break
                    continue

                except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                    last_error = exc
                    log.warning("Gemini %s network error (attempt %d): %r", model, attempt + 1, exc)
                    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
                        break  # a model that timed out once will likely do it again; try the next one
                    await asyncio.sleep(min(2 ** attempt * 3, 30))
                    continue

        raise LLMError(f"Gemini could not complete the request: {last_error}")
