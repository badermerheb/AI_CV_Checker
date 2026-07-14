"""Langfuse tracing helpers (SDK v4 API). No-ops gracefully when keys are not configured."""

from contextlib import nullcontext
from functools import lru_cache

from langfuse import Langfuse, propagate_attributes

from app.config import settings


@lru_cache
def get_langfuse() -> Langfuse | None:
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def span(name: str, **kwargs):
    lf = get_langfuse()
    if not lf:
        return nullcontext(None)
    return lf.start_as_current_observation(name=name, as_type="span", **kwargs)


def retriever(name: str, **kwargs):
    lf = get_langfuse()
    if not lf:
        return nullcontext(None)
    return lf.start_as_current_observation(name=name, as_type="retriever", **kwargs)


def generation(name: str, **kwargs):
    lf = get_langfuse()
    if not lf:
        return nullcontext(None)
    return lf.start_as_current_observation(name=name, as_type="generation", **kwargs)


def session(session_id: str):
    """Attach a session id to every span created inside this context."""
    return propagate_attributes(session_id=session_id) if get_langfuse() else nullcontext(None)


def flush() -> None:
    lf = get_langfuse()
    if lf:
        lf.flush()
