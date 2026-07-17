"""Qdrant hybrid index (dense BGE + sparse BM25) via LlamaIndex."""

from functools import lru_cache

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels

from app.chunking import Chunk
from app.config import settings
from app.embeddings import LocalFastEmbedEmbedding

COLLECTION = "cv_chunks"
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"

# Keys that must not pollute the text used for embedding or LLM prompts.
_HIDDEN_METADATA_KEYS = ["candidate_id", "filename", "chunk_index", "page", "workspace_id"]


@lru_cache
def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


@lru_cache
def get_index() -> VectorStoreIndex:
    vector_store = QdrantVectorStore(
        client=get_client(),
        collection_name=COLLECTION,
        enable_hybrid=True,
        fastembed_sparse_model=SPARSE_MODEL,
    )
    return VectorStoreIndex.from_vector_store(
        vector_store,
        embed_model=LocalFastEmbedEmbedding(model_name=DENSE_MODEL),
    )


def ensure_payload_indexes(client: QdrantClient | None = None) -> None:
    """Qdrant Cloud requires payload indexes for filtered fields (strict mode)."""
    client = client or get_client()
    if not client.collection_exists(COLLECTION):
        return
    for field in ("workspace_id", "candidate_id", "candidate_name"):
        try:
            client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # already exists


def index_chunks(
    chunks: list[Chunk], candidate_id: str, candidate_name: str, filename: str, workspace_id: str
) -> int:
    nodes = []
    for chunk in chunks:
        node = TextNode(
            text=chunk.text,
            metadata={
                "workspace_id": workspace_id,
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "filename": filename,
                "section": chunk.section,
                "chunk_index": chunk.chunk_index,
                "page": chunk.page,
            },
        )
        node.excluded_embed_metadata_keys = _HIDDEN_METADATA_KEYS
        node.excluded_llm_metadata_keys = _HIDDEN_METADATA_KEYS
        nodes.append(node)
    get_index().insert_nodes(nodes)
    ensure_payload_indexes()
    return len(nodes)


def delete_candidate_points(candidate_id: str, workspace_id: str) -> None:
    client = get_client()
    if not client.collection_exists(COLLECTION):
        return
    client.delete(
        collection_name=COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="candidate_id", match=qmodels.MatchValue(value=candidate_id)
                    ),
                    qmodels.FieldCondition(
                        key="workspace_id", match=qmodels.MatchValue(value=workspace_id)
                    ),
                ]
            )
        ),
    )


def count_points(workspaces: list[str] | None = None) -> int:
    client = get_client()
    if not client.collection_exists(COLLECTION):
        return 0
    count_filter = None
    if workspaces:
        count_filter = qmodels.Filter(
            must=[qmodels.FieldCondition(key="workspace_id", match=qmodels.MatchAny(any=workspaces))]
        )
    return client.count(COLLECTION, count_filter=count_filter).count
