"""Provider factory: one generator (Gemini) and one independent verifier (Groq)."""

from __future__ import annotations

from app.config import get_settings
from app.services.llm.base import JSONGenerator, LLMError, LLMNotConfigured

_generator: JSONGenerator | None = None
_verifier: JSONGenerator | None = None
_verifier_checked = False


def get_generator() -> JSONGenerator:
    global _generator
    if _generator is None:
        s = get_settings()
        if s.is_fake_llm:
            from app.services.llm.fake import FakeGenerator

            _generator = FakeGenerator("fake-generator")
        else:
            from app.services.llm.gemini import GeminiGenerator

            _generator = GeminiGenerator(
                s.gemini_api_key, s.gemini_model_list, rpm=s.gemini_rpm, thinking_level=s.gemini_thinking
            )
    return _generator


def get_verifier() -> JSONGenerator | None:
    """Returns None when no verifier is configured (items are then only quote-checked)."""
    global _verifier, _verifier_checked
    if not _verifier_checked:
        _verifier_checked = True
        s = get_settings()
        if s.is_fake_llm:
            from app.services.llm.fake import FakeGenerator

            _verifier = FakeGenerator("fake-verifier")
        elif s.groq_api_key:
            from app.services.llm.groq_client import GroqGenerator

            _verifier = GroqGenerator(s.groq_api_key, s.groq_model_list, rpm=s.groq_rpm, tpm=s.groq_tpm)
    return _verifier


def reset_providers() -> None:
    """For tests."""
    global _generator, _verifier, _verifier_checked
    _generator, _verifier, _verifier_checked = None, None, False


__all__ = ["JSONGenerator", "LLMError", "LLMNotConfigured", "get_generator", "get_verifier", "reset_providers"]
