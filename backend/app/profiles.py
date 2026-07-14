"""Structured candidate-profile extraction from raw CV text via Gemini."""

from google.genai import errors as genai_errors
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import generate_with_retry


class EducationItem(BaseModel):
    degree: str = ""
    school: str = ""
    year: str = ""


class CandidateProfile(BaseModel):
    name: str = Field(description="Candidate's full name exactly as written in the CV")
    current_title: str = Field(default="", description="Current or most recent job title")
    years_experience: float = Field(
        default=0, description="Total years of professional experience, estimated from employment dates"
    )
    location: str = ""
    skills: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list, description="Spoken languages with proficiency")
    certifications: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="One-sentence recruiter-facing summary of the candidate")


class ProfileExtractionError(Exception):
    pass


_PROMPT = """You are an assistant for technical recruiters. Below is the full text of one \
candidate's CV/resume. Extract the candidate's profile following the JSON schema exactly.

Rules:
- Only use facts present in the CV text. Never invent or embellish; use "" or [] when absent.
- years_experience: estimate the total from the employment dates (internships included).
- skills: list technical and professional skills explicitly mentioned anywhere in the CV.

CV text:
\"\"\"
{cv_text}
\"\"\"
"""

def extract_profile(cv_text: str) -> CandidateProfile:
    try:
        response = generate_with_retry(
            model=settings.gemini_model,
            contents=_PROMPT.format(cv_text=cv_text),
            config={
                "response_mime_type": "application/json",
                "response_schema": CandidateProfile,
                "temperature": 0,
            },
        )
    except genai_errors.APIError as exc:
        raise ProfileExtractionError(f"Gemini API error {exc.code}: {exc.message}") from exc
    profile = response.parsed
    if isinstance(profile, CandidateProfile) and profile.name.strip():
        return profile
    raise ProfileExtractionError("model returned an empty or invalid profile")
