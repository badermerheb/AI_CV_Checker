"""LlamaIndex embedding adapter backed by fastembed (ONNX, CPU-friendly).

The official llama-index-embeddings-fastembed package pins Python <3.13,
so this small adapter wraps fastembed directly instead.
"""

from typing import Any

from fastembed import TextEmbedding
from llama_index.core.base.embeddings.base import BaseEmbedding
from pydantic import PrivateAttr


class LocalFastEmbedEmbedding(BaseEmbedding):
    _model: Any = PrivateAttr()

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", **kwargs: Any) -> None:
        super().__init__(model_name=model_name, **kwargs)
        self._model = TextEmbedding(model_name=model_name)

    @classmethod
    def class_name(cls) -> str:
        return "LocalFastEmbedEmbedding"

    def _get_query_embedding(self, query: str) -> list[float]:
        return next(iter(self._model.query_embed(query))).tolist()

    def _get_text_embedding(self, text: str) -> list[float]:
        return next(iter(self._model.passage_embed([text]))).tolist()

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        # One at a time on purpose: onnxruntime's memory arena grows to the largest
        # batch ever embedded and never shrinks, which OOMs 512 MB free-tier hosts
        # during ingestion (queries are single texts and unaffected).
        return [next(iter(self._model.passage_embed([text]))).tolist() for text in texts]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)
