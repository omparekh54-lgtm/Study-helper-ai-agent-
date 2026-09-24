"""Shared LLM plumbing: rate limiting, JSON extraction and error types."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections import deque
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The provider failed after retries (quota, outage, bad output)."""


class LLMNotConfigured(LLMError):
    """No API key configured for this provider."""


class JSONGenerator(Protocol):
    name: str

    async def generate_json(
        self, *, system: str, prompt: str, schema: type[T], max_output_tokens: int = 8192, fast: bool = False
    ) -> T: ...


class RateLimiter:
    """Sliding-window limiter for requests-per-minute and (optionally) tokens-per-minute.

    Free tiers enforce both; staying just under them avoids a storm of 429s.
    """

    def __init__(self, rpm: int, tpm: int | None = None, window: float = 60.0):
        self.rpm = max(1, rpm)
        self.tpm = tpm
        self.window = window
        self._events: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 0) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._events and now - self._events[0][0] >= self.window:
                    self._events.popleft()
                used = sum(t for _, t in self._events)
                fits_tokens = self.tpm is None or not self._events or used + tokens <= self.tpm
                if len(self._events) < self.rpm and fits_tokens:
                    self._events.append((now, tokens))
                    return
                wait = self.window - (now - self._events[0][0]) + 0.05
            await asyncio.sleep(min(max(wait, 0.2), self.window))


def estimate_tokens(*texts: str) -> int:
    return sum(len(t) for t in texts) // 4 + 50


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(text: str) -> object:
    """Parse JSON from a model reply, tolerating code fences and leading/trailing prose."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    stripped = _FENCE.sub("", text).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = min((i for i in (stripped.find("{"), stripped.find("[")) if i != -1), default=-1)
    end = max(stripped.rfind("}"), stripped.rfind("]"))
    if start != -1 and end > start:
        return json.loads(stripped[start : end + 1])
    raise ValueError("No JSON object found in model output")


def parse_model(text: str, schema: type[T]) -> T:
    try:
        return schema.model_validate(extract_json(text))
    except (ValueError, ValidationError) as exc:
        raise ValueError(f"Model output did not match the expected format: {exc}") from exc


def retry_delay_from_text(text: str, default: float) -> float:
    """Pull a server-suggested delay ('retryDelay': '31s' / 'try again in 7.5s') out of an error."""
    m = re.search(r"retry(?:Delay)?['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", text, re.IGNORECASE)
    if not m:
        m = re.search(r"try again in (\d+(?:\.\d+)?)s", text, re.IGNORECASE)
    if m:
        return min(float(m.group(1)) + 1.0, 90.0)
    return default
