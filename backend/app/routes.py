"""API routes: CV upload/ingestion and candidate listing."""

import hashlib
import re

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import db, vectorstore
from app.chunking import chunk_cv
from app.parsing import ParseError, parse_document
from app.profiles import ProfileExtractionError, extract_profile

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_BYTES = 10 * 1024 * 1024
MIN_TEXT_CHARS = 80


class IngestError(Exception):
    pass


def make_candidate_id(name: str, filename: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "candidate"
    digest = hashlib.sha1(filename.lower().encode()).hexdigest()[:6]
    return f"{slug}-{digest}"


def _ingest_one(upload: UploadFile) -> dict:
    filename = upload.filename or "unnamed"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestError(f"unsupported file type '{ext}' (accepted: .pdf, .docx)")

    data = upload.file.read()
    if len(data) > MAX_FILE_BYTES:
        raise IngestError("file exceeds the 10 MB limit")

    try:
        pages = parse_document(data, filename)
    except ParseError as exc:
        raise IngestError(str(exc)) from exc
    text = "\n".join(pages).strip()
    if len(text) < MIN_TEXT_CHARS:
        raise IngestError("no extractable text (scanned image-only PDF?)")

    try:
        profile = extract_profile(text)
    except ProfileExtractionError as exc:
        raise IngestError(f"profile extraction failed: {exc}") from exc

    candidate_id = make_candidate_id(profile.name, filename)

    # Idempotent re-upload: drop anything previously ingested from this file
    # (or under this candidate_id) before indexing fresh.
    for stale_id in {*db.delete_by_filename(filename), candidate_id}:
        vectorstore.delete_candidate_points(stale_id)

    chunks = chunk_cv(text, pages)
    if not chunks:
        raise IngestError("document produced no usable chunks")
    num_indexed = vectorstore.index_chunks(chunks, candidate_id, profile.name, filename)
    db.upsert_candidate(candidate_id, profile.model_dump(), filename, num_indexed)

    return {
        "filename": filename,
        "status": "ok",
        "candidate_id": candidate_id,
        "name": profile.name,
        "title": profile.current_title,
        "chunks_indexed": num_indexed,
    }


@router.post("/upload")
def upload_cvs(files: list[UploadFile] = File(...)) -> dict:
    results = []
    for upload in files:
        try:
            results.append(_ingest_one(upload))
        except IngestError as exc:
            results.append({"filename": upload.filename, "status": "error", "detail": str(exc)})
    return {"results": results}


@router.get("/candidates")
def candidates() -> dict:
    return {"candidates": db.list_candidates()}


@router.get("/candidates/{candidate_id}")
def candidate_detail(candidate_id: str) -> dict:
    candidate = db.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return candidate


@router.get("/stats")
def stats() -> dict:
    return {"candidates": db.count_candidates(), "chunks_indexed": vectorstore.count_points()}
