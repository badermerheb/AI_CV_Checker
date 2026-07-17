"""API routes: CV upload/ingestion and candidate listing."""

import hashlib
import re

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

from app import db, vectorstore
from app.chat import ChatError, chat, workspace_scope
from app.chunking import chunk_cv
from app.config import settings
from app.parsing import ParseError, parse_document
from app.profiles import ProfileExtractionError, extract_profile

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_BYTES = 10 * 1024 * 1024
MIN_TEXT_CHARS = 80

_WORKSPACE_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _workspace(header_value: str | None) -> str:
    """Anonymous per-browser workspace id from the X-Workspace-Id header."""
    if header_value and _WORKSPACE_RE.fullmatch(header_value):
        return header_value
    return "demo"


class IngestError(Exception):
    pass


def make_candidate_id(name: str, filename: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "candidate"
    digest = hashlib.sha1(filename.lower().encode()).hexdigest()[:6]
    return f"{slug}-{digest}"


def _ingest_one(upload: UploadFile, workspace_id: str) -> dict:
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
    # (or under this candidate_id) in THIS workspace before indexing fresh.
    for stale_id in {*db.delete_by_filename(workspace_id, filename), candidate_id}:
        vectorstore.delete_candidate_points(stale_id, workspace_id)

    chunks = chunk_cv(text, pages)
    if not chunks:
        raise IngestError("document produced no usable chunks")
    num_indexed = vectorstore.index_chunks(chunks, candidate_id, profile.name, filename, workspace_id)
    db.upsert_candidate(workspace_id, candidate_id, profile.model_dump(), filename, num_indexed)

    return {
        "filename": filename,
        "status": "ok",
        "candidate_id": candidate_id,
        "name": profile.name,
        "title": profile.current_title,
        "chunks_indexed": num_indexed,
    }


@router.post("/upload")
def upload_cvs(
    files: list[UploadFile] = File(...),
    x_workspace_id: str | None = Header(default=None),
) -> dict:
    workspace_id = _workspace(x_workspace_id)
    if workspace_id == "demo" and not settings.allow_demo_writes:
        raise HTTPException(
            status_code=403,
            detail="The shared demo corpus is read-only. Uploads go to your own workspace "
            "(the app sends it automatically).",
        )
    results = []
    for upload in files:
        try:
            results.append(_ingest_one(upload, workspace_id))
        except IngestError as exc:
            results.append({"filename": upload.filename, "status": "error", "detail": str(exc)})
    return {"results": results}


@router.get("/candidates")
def candidates(x_workspace_id: str | None = Header(default=None)) -> dict:
    workspaces = workspace_scope(_workspace(x_workspace_id))
    return {"candidates": db.list_candidates(workspaces)}


@router.get("/candidates/{candidate_id}")
def candidate_detail(candidate_id: str, x_workspace_id: str | None = Header(default=None)) -> dict:
    workspace_id = _workspace(x_workspace_id)
    candidate = db.get_candidate(candidate_id, workspace_scope(workspace_id), prefer=workspace_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return candidate


@router.get("/stats")
def stats(x_workspace_id: str | None = Header(default=None)) -> dict:
    workspaces = workspace_scope(_workspace(x_workspace_id))
    return {
        "candidates": db.count_candidates(workspaces),
        "chunks_indexed": vectorstore.count_points(workspaces),
    }


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
def chat_endpoint(request: ChatRequest, x_workspace_id: str | None = Header(default=None)) -> dict:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must not be empty")
    try:
        return chat(message, request.session_id, workspace_id=_workspace(x_workspace_id))
    except ChatError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
