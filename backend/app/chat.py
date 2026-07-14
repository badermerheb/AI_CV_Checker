"""Chat over the indexed CVs: retrieve -> prompt -> Gemini -> answer with citations.

Phase 2 baseline: dense-only top-5 retrieval, no reranking. Hybrid + reranker
land in the retrieval-upgrades phase so the eval harness can measure the delta.
"""

import time
import uuid

from google.genai import errors as genai_errors
from google.genai import types as genai_types
from llama_index.core.schema import MetadataMode, NodeWithScore

from app import db, tracing, vectorstore
from app.config import settings
from app.llm import generate_with_retry

TOP_K = 5
HISTORY_TURNS = 6  # messages of prior conversation included in the prompt

SYSTEM_PROMPT = """You are an assistant for recruiters, answering questions about the \
candidate CVs/resumes that have been uploaded.

Rules:
- Answer ONLY from the numbered CV excerpts provided in the message. Do not use outside knowledge \
about people or companies.
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


def chat(message: str, session_id: str | None) -> dict:
    session_id = session_id or uuid.uuid4().hex
    started = time.perf_counter()

    with tracing.session(session_id), tracing.span("chat", input={"message": message}) as root:
        with tracing.retriever("retrieval", input=message) as retrieval_span:
            retriever = vectorstore.get_index().as_retriever(similarity_top_k=TOP_K)
            nodes = retriever.retrieve(message)
            if retrieval_span:
                retrieval_span.update(
                    output=[
                        {
                            "candidate": n.node.metadata.get("candidate_name"),
                            "section": n.node.metadata.get("section"),
                            "score": n.score,
                        }
                        for n in nodes
                    ]
                )

        context_block, citations = _format_context(nodes)
        history = db.get_history(session_id, limit=HISTORY_TURNS)
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
            root.update(output={"answer": answer, "latency_ms": latency_ms})

    tracing.flush()
    return {
        "session_id": session_id,
        "answer": answer,
        "citations": citations,
        "latency_ms": latency_ms,
    }
