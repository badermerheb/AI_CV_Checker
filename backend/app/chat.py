"""Chat over the indexed CVs: route -> retrieve -> Gemini -> answer with citations.

The pipeline is configurable (dense/hybrid, rerank on/off, routing on/off) so the
eval harness can measure each upgrade; the API serves the settings defaults.
"""

import time
import uuid
from collections import defaultdict
from statistics import mean

from google.genai import errors as genai_errors
from google.genai import types as genai_types
from llama_index.core.schema import MetadataMode, NodeWithScore

from app import db, tracing, vectorstore
from app.config import settings
from app.llm import generate_with_retry
from app.retrieval import rerank_nodes, retrieve
from app.router import RouteDecision, route

TOP_K = 5
HISTORY_TURNS = 6  # messages of prior conversation included in the prompt
JOBFIT_POOL = 50  # chunks fetched across all candidates before aggregation
JOBFIT_SHORTLIST = 5  # candidates surfaced to the LLM

SYSTEM_PROMPT = """You are an assistant for recruiters, answering questions about the \
candidate CVs/resumes that have been uploaded.

Rules:
- Answer ONLY from the numbered CV excerpts (and candidate profiles, when provided) in the \
message. Do not use outside knowledge about people or companies.
- Cite your evidence inline with bracketed excerpt numbers, e.g. [1] or [2][3], right after the \
claim they support. Every factual claim about a candidate needs a citation.
- If the excerpts do not contain the answer, say plainly that the uploaded CVs don't contain that \
information. Never guess or invent.
- Be concise. Use short paragraphs or bullet points."""


class ChatError(Exception):
    pass


def _format_context(nodes: list[NodeWithScore]) -> tuple[str, list[dict]]:
    blocks: list[str] = []
    citations: list[dict] = []
    for i, node_with_score in enumerate(nodes, start=1):
        meta = node_with_score.node.metadata
        text = node_with_score.node.get_content(metadata_mode=MetadataMode.NONE).strip()
        source = f"{meta.get('candidate_name', '?')} — {meta.get('section') or 'CV'}"
        blocks.append(f"[{i}] {source} ({meta.get('filename', '')})\n{text}")
        citations.append(
            {
                "n": i,
                "candidate_id": meta.get("candidate_id"),
                "candidate_name": meta.get("candidate_name"),
                "filename": meta.get("filename"),
                "section": meta.get("section"),
                "page": meta.get("page"),
                "score": round(node_with_score.score, 4) if node_with_score.score is not None else None,
                "snippet": text,
            }
        )
    return "\n\n".join(blocks), citations


def _jobfit_nodes(
    query: str, *, mode: str, rerank: bool, workspaces: list[str]
) -> tuple[list[NodeWithScore], list[dict]]:
    """Best-fit ranking is aggregation, not plain top-k: score candidates by their
    best chunks against the job description, then surface a shortlist."""
    pool = retrieve(
        query, mode=mode, rerank=False, top_k=JOBFIT_POOL, fetch_k=JOBFIT_POOL, workspaces=workspaces
    )

    # Key by (workspace, candidate) - the same CV can exist in demo and a user workspace.
    by_candidate: dict[tuple[str, str], list[NodeWithScore]] = defaultdict(list)
    for node in pool:
        meta = node.node.metadata
        key = (meta.get("workspace_id", "demo"), meta.get("candidate_id", "?"))
        by_candidate[key].append(node)

    def candidate_score(nodes: list[NodeWithScore]) -> float:
        scores = sorted((n.score or 0.0 for n in nodes), reverse=True)
        return mean(scores[:3])

    shortlist = sorted(by_candidate, key=lambda c: candidate_score(by_candidate[c]), reverse=True)
    shortlist = shortlist[:JOBFIT_SHORTLIST]

    nodes: list[NodeWithScore] = []
    for key in shortlist:
        best = sorted(by_candidate[key], key=lambda n: n.score or 0.0, reverse=True)[:2]
        nodes.extend(best)
    if rerank and len(nodes) > 2:
        nodes = rerank_nodes(query, nodes, top_k=min(8, len(nodes)))

    profiles = [
        p for ws, cid in shortlist if (p := db.get_candidate(cid, workspaces=[ws], prefer=ws))
    ]
    return nodes, profiles


def _profiles_block(profiles: list[dict]) -> str:
    lines = []
    for p in profiles:
        prof = p["profile"]
        lines.append(
            f"- {p['name']} — {p['current_title']}, {p['years_experience']} yrs, "
            f"{p['location']}. Skills: {', '.join(prof.get('skills', [])[:12])}"
        )
    return "\n".join(lines)


def workspace_scope(workspace_id: str) -> list[str]:
    """A user sees their own uploads plus the shared demo corpus."""
    return [workspace_id] if workspace_id == "demo" else [workspace_id, "demo"]


def gather_context(
    message: str,
    history: list[dict],
    *,
    mode: str,
    rerank: bool,
    routing: bool,
    workspace_id: str = "demo",
) -> tuple[list[NodeWithScore], list[dict], RouteDecision]:
    """Route the question and fetch its context. Shared by chat() and the eval harness."""
    workspaces = workspace_scope(workspace_id)
    decision = RouteDecision()
    if routing:
        known = [c["name"] for c in db.list_candidates(workspaces)]
        decision = route(message, history, known)

    profiles: list[dict] = []
    if decision.intent == "single_candidate":
        nodes = retrieve(
            message, mode=mode, rerank=rerank, top_k=TOP_K,
            candidate_names=decision.candidate_names, workspaces=workspaces,
        )
    elif decision.intent == "job_fit":
        nodes, profiles = _jobfit_nodes(message, mode=mode, rerank=rerank, workspaces=workspaces)
    else:
        nodes = retrieve(message, mode=mode, rerank=rerank, top_k=TOP_K, workspaces=workspaces)
    return nodes, profiles, decision


def _build_contents(history: list[dict], user_message: str) -> list[genai_types.Content]:
    contents = [
        genai_types.Content(
            role="user" if msg["role"] == "user" else "model",
            parts=[genai_types.Part.from_text(text=msg["content"])],
        )
        for msg in history
    ]
    contents.append(
        genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=user_message)])
    )
    return contents


def chat(
    message: str,
    session_id: str | None,
    *,
    mode: str | None = None,
    rerank: bool | None = None,
    routing: bool | None = None,
    workspace_id: str = "demo",
) -> dict:
    mode = settings.retrieval_mode if mode is None else mode
    rerank = settings.rerank if rerank is None else rerank
    routing = settings.routing if routing is None else routing

    session_id = session_id or uuid.uuid4().hex
    started = time.perf_counter()

    with tracing.session(session_id), tracing.span(
        "chat", input={"message": message}, metadata={"mode": mode, "rerank": rerank, "routing": routing}
    ) as root:
        history = db.get_history(session_id, limit=HISTORY_TURNS)

        with tracing.retriever("route+retrieve", input=message) as retrieval_span:
            nodes, profiles, decision = gather_context(
                message, history, mode=mode, rerank=rerank, routing=routing,
                workspace_id=workspace_id,
            )
            if retrieval_span:
                retrieval_span.update(
                    output={
                        "intent": decision.intent,
                        "candidates": decision.candidate_names,
                        "chunks": [
                            {
                                "candidate": n.node.metadata.get("candidate_name"),
                                "section": n.node.metadata.get("section"),
                                "score": n.score,
                            }
                            for n in nodes
                        ],
                    }
                )

        context_block, citations = _format_context(nodes)
        if decision.intent == "job_fit":
            user_message = (
                f"Job requirement: {message}\n\n"
                f"Candidate profiles (extracted from CVs):\n{_profiles_block(profiles)}\n\n"
                f"CV excerpts:\n{context_block}\n\n"
                "Rank the best-fitting candidates for this job requirement, best first, with a "
                "short justification each. Cite excerpt numbers for every claim."
            )
        else:
            user_message = f"CV excerpts:\n{context_block}\n\nQuestion: {message}"

        with tracing.generation(
            "answer", model=settings.gemini_model, input={"system": SYSTEM_PROMPT, "user": user_message}
        ) as gen:
            try:
                response = generate_with_retry(
                    model=settings.gemini_model,
                    contents=_build_contents(history, user_message),
                    config={"system_instruction": SYSTEM_PROMPT, "temperature": 0.2},
                )
            except genai_errors.APIError as exc:
                raise ChatError(f"LLM error {exc.code}: {getattr(exc, 'message', exc)}") from exc
            answer = (response.text or "").strip()
            if gen:
                usage = getattr(response, "usage_metadata", None)
                gen.update(
                    output=answer,
                    usage_details={
                        "input": getattr(usage, "prompt_token_count", None) or 0,
                        "output": getattr(usage, "candidates_token_count", None) or 0,
                    },
                )

        if not answer:
            raise ChatError("model returned an empty answer")

        db.add_message(session_id, "user", message)
        db.add_message(session_id, "assistant", answer)

        latency_ms = int((time.perf_counter() - started) * 1000)
        if root:
            root.set_trace_io(input=message, output=answer)
            root.update(output={"answer": answer, "latency_ms": latency_ms, "intent": decision.intent})

    tracing.flush()
    return {
        "session_id": session_id,
        "answer": answer,
        "citations": citations,
        "latency_ms": latency_ms,
        "intent": decision.intent,
    }
