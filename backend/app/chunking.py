"""Section-aware CV chunking with a sentence-splitter fallback.

CVs are split at recognizable section headers (Experience, Education, ...);
each chunk remembers its section for citation labels. CVs with no detectable
structure fall back to plain sentence splitting with section=None.
"""

import re
from dataclasses import dataclass

from llama_index.core.node_parser import SentenceSplitter

CANONICAL_SECTIONS = {
    "summary": ("summary", "professional summary", "profile", "about", "about me", "objective"),
    "experience": ("experience", "work experience", "professional experience",
                   "employment", "employment history", "work history"),
    "education": ("education", "academic background", "academics"),
    "skills": ("skills", "technical skills", "core skills", "skills & tools", "competencies"),
    "languages": ("languages",),
    "certifications": ("certifications", "certificates", "licenses",
                       "licenses & certifications"),
    "projects": ("projects", "personal projects", "selected projects"),
    "contact": ("contact", "contact information", "contact details"),
    "other": ("awards", "honors", "publications", "interests", "volunteering", "references"),
}
_ALIAS_TO_SECTION = {
    alias: canonical
    for canonical, aliases in CANONICAL_SECTIONS.items()
    for alias in aliases
}
# A header is a short standalone line of words, optionally ending with ":".
_HEADER_RE = re.compile(r"^[\s•\-–]*([A-Za-z][A-Za-z &/]{1,35}?)\s*:?\s*$")

# Sections longer than this get sub-split; also the fallback splitter config.
MAX_SECTION_CHARS = 1800
_splitter = SentenceSplitter(chunk_size=350, chunk_overlap=40)

MIN_CHUNK_CHARS = 25


@dataclass
class Chunk:
    text: str
    section: str | None
    chunk_index: int
    page: int | None


def _header_of(line: str) -> str | None:
    match = _HEADER_RE.match(line)
    if not match:
        return None
    return _ALIAS_TO_SECTION.get(match.group(1).strip().lower())


def _split_sections(text: str) -> list[tuple[str | None, str]] | None:
    """Split at detected headers. Returns None if fewer than 2 headers found."""
    lines = text.splitlines()
    bounds = [(i, section) for i, line in enumerate(lines) if (section := _header_of(line))]
    if len(bounds) < 2:
        return None
    segments: list[tuple[str | None, str]] = []
    head = "\n".join(lines[: bounds[0][0]]).strip()
    if head:
        segments.append((None, head))  # name/title/contact block before first header
    for (start, section), (end, _) in zip(bounds, bounds[1:] + [(len(lines), None)]):
        body = "\n".join(lines[start:end]).strip()  # header line kept for context
        if body:
            segments.append((section, body))
    return segments


def _page_of(chunk_text: str, pages: list[str]) -> int | None:
    if len(pages) == 1:
        return 1
    probe = chunk_text.strip()[:60]
    for page_num, page_text in enumerate(pages, start=1):
        if probe and probe in page_text:
            return page_num
    return None


def chunk_cv(text: str, pages: list[str]) -> list[Chunk]:
    segments = _split_sections(text) or [(None, text)]
    chunks: list[Chunk] = []
    for section, segment in segments:
        parts = _splitter.split_text(segment) if len(segment) > MAX_SECTION_CHARS else [segment]
        for part in parts:
            part = part.strip()
            if len(part) < MIN_CHUNK_CHARS:
                continue
            chunks.append(
                Chunk(text=part, section=section, chunk_index=len(chunks), page=_page_of(part, pages))
            )
    return chunks
