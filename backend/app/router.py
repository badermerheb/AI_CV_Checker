"""Intent routing: classify each question so retrieval can be candidate-filtered
(single-candidate questions) or aggregated per candidate (job-fit questions)."""

from typing import Literal

from google.genai import errors as genai_errors
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import generate_with_retry


class RouteDecision(BaseModel):
    intent: Literal["single_candidate", "job_fit", "general"] = "general"
    candidate_names: list[str] = Field(
        default_factory=list,
        description="Exact names from the known-candidates list this question is about",
    )


_PROMPT = """Classify a recruiter's question about a set of uploaded candidate CVs.

Known candidates:
{names}

Recent conversation (may resolve pronouns like "she" or "his"):
{history}

Question: {question}

Intents:
- single_candidate: the question is about one or more SPECIFIC candidates, named directly \
or referred to by pronoun. Fill candidate_names with their exact names from the known list.
- job_fit: the question asks who fits, matches, or should be shortlisted/hired for a job, \
role, or hiring need.
- general: anything else - skill searches, comparisons, counts, locations, languages.
"""


def route(question: str, history: list[dict], known_names: list[str]) -> RouteDecision:
    history_text = (
        "\n".join(f"{m['role']}: {m['content'][:300]}" for m in history[-4:]) or "(none)"
    )
    try:
        response = generate_with_retry(
            model=settings.gemini_model,
            contents=_PROMPT.format(
                names="\n".join(f"- {n}" for n in known_names),
                history=history_text,
                question=question,
            ),
            config={
                "response_mime_type": "application/json",
                "response_schema": RouteDecision,
                "temperature": 0,
            },
        )
        decision = response.parsed
        if not isinstance(decision, RouteDecision):
            return RouteDecision()
    except genai_errors.APIError:
        return RouteDecision()  # routing is an optimization; fail open to general

    # Keep only names that actually exist (exact, case-insensitive match).
    lookup = {n.lower(): n for n in known_names}
    decision.candidate_names = [
        lookup[n.lower()] for n in decision.candidate_names if n.lower() in lookup
    ]
    if decision.intent == "single_candidate" and not decision.candidate_names:
        decision.intent = "general"
    return decision
