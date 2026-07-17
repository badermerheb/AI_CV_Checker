"""Configurable retrieval: dense or hybrid (dense+BM25), optional cross-encoder rerank,
optional per-candidate metadata filtering."""

from functools import lru_cache

from llama_index.core.schema import MetadataMode, NodeWithScore
from llama_index.core.vector_stores import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)

from app import vectorstore
from app.config import settings


@lru_cache
def _cross_encoder():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=settings.rerank_model)


def rerank_nodes(query: str, nodes: list[NodeWithScore], top_k: int) -> list[NodeWithScore]:
    # Chunk text alone often lacks the candidate's name (it lives in metadata), so a
    # bare cross-encoder can't tell WHOSE education/languages it is ranking. Prefix
    # identity so name-specific queries rank the right person's sections first.
    texts = [
        f"{n.node.metadata.get('candidate_name', '')} — {n.node.metadata.get('section') or 'CV'}: "
        f"{n.node.get_content(metadata_mode=MetadataMode.NONE)}"
        for n in nodes
    ]
    scores = list(_cross_encoder().rerank(query, texts))
    ranked = sorted(zip(nodes, scores), key=lambda pair: pair[1], reverse=True)
    reranked = []
    for node, score in ranked[:top_k]:
        node.score = float(score)
        reranked.append(node)
    return reranked


def retrieve(
    query: str,
    *,
    mode: str = "dense",
    top_k: int = 5,
    fetch_k: int | None = None,
    rerank: bool = False,
    candidate_names: list[str] | None = None,
    workspaces: list[str] | None = None,
) -> list[NodeWithScore]:
    index = vectorstore.get_index()
    fetch_k = fetch_k or settings.fetch_k
    k = fetch_k if rerank else top_k

    filters: list[MetadataFilter] = []
    if workspaces:
        filters.append(
            MetadataFilter(key="workspace_id", operator=FilterOperator.IN, value=workspaces)
        )
    if candidate_names:
        filters.append(
            MetadataFilter(key="candidate_name", operator=FilterOperator.IN, value=candidate_names)
        )
    kwargs: dict = {}
    if filters:
        kwargs["filters"] = MetadataFilters(filters=filters)

    if mode == "hybrid":
        retriever = index.as_retriever(
            vector_store_query_mode="hybrid",
            similarity_top_k=k,
            sparse_top_k=k,
            hybrid_top_k=k,
            **kwargs,
        )
    else:
        retriever = index.as_retriever(similarity_top_k=k, **kwargs)

    nodes = retriever.retrieve(query)
    if rerank and len(nodes) > top_k:
        nodes = rerank_nodes(query, nodes, top_k)
    return nodes[:top_k]
