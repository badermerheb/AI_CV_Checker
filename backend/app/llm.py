"""Shared Gemini client with free-tier-aware retry."""

import time
from functools import lru_cache
from typing import Any

from google import genai
from google.genai import errors as genai_errors

from app.config import settings

_RETRYABLE_CODES = {429, 500, 503}
_MAX_ATTEMPTS = 4


@lru_cache
def get_genai_client() -> genai.Client:
    return genai.Client(api_key=settings.google_api_key)


def generate_with_retry(**kwargs: Any):
    """generate_content with exponential backoff on rate limits / transient errors."""
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return get_genai_client().models.generate_content(**kwargs)
        except genai_errors.APIError as exc:
            last_error = exc
            if exc.code == 429 and "PerDay" in str(exc):
                raise  # daily quota exhausted - retrying cannot help
            if exc.code in _RETRYABLE_CODES and attempt < _MAX_ATTEMPTS - 1:
                time.sleep(15 * (attempt + 1))
                continue
            raise
    raise last_error  # unreachable, keeps type-checkers happy
