# AI CV Checker

A production-grade RAG app for recruiters: upload CVs/resumes, then chat with them —
"Who best fits this job description?", "Tell me about candidate X", or general questions
across all CVs. Answers come with inline citations back to the source CVs.

> Work in progress — see [PLAN.md](PLAN.md) for the full build plan and progress.

## Stack

React + Vite (frontend) · FastAPI + LlamaIndex (backend) · Qdrant (hybrid vector + keyword search)
· BGE embeddings + cross-encoder reranker (local) · Gemini (LLM) · RAGAS (evaluation) · Langfuse (tracing)

## Architecture

```
React (Vite + TS)  ──/api──►  FastAPI + LlamaIndex
  Chat · Candidates · Upload     │
                                 ├─ INGEST  parse (PyMuPDF) → section-aware chunking
                                 │          → Gemini profile extraction (structured JSON)
                                 │          → Qdrant (BGE dense + BM25 sparse)
                                 │
                                 ├─ CHAT    intent router (single-candidate / job-fit / general)
                                 │          → hybrid retrieval (+ candidate filters)
                                 │          → cross-encoder rerank
                                 │          → per-candidate aggregation for job-fit
                                 │          → Gemini answer with inline [n] citations
                                 │
                                 ├─ Langfuse traces on every request
                                 └─ SQLite: candidate profiles + chat sessions
Qdrant in Podman (dev) / Qdrant Cloud (prod)
```

## Evaluation results

Measured on a hand-built gold set: 30 verified questions over 16 fixed sample CVs
(details and metric rationale in [eval/README.md](eval/README.md)).

| config | section-hit@5 | recall@5 | MRR |
|---|---|---|---|
| baseline (dense top-5) | 82.6% | 96.7% | 0.90 |
| + hybrid (BM25 fusion) | **100%** | 96.7% | 0.95 |
| + cross-encoder rerank | 100% | 98.3% | 0.98 |
| + intent routing & job-fit aggregation | 100% | **100%** | 0.98 |

`section-hit@5` = the chunk that actually contains the answer was retrieved (file-level
hit-rate saturates at ~97-100% on a corpus this size). Faithfulness / relevancy (RAGAS)
and latency per config live in [eval/results/comparison.md](eval/results/comparison.md).

## Run locally (dev)

```bash
# 1. Qdrant (Podman or Docker)
podman run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env                              # then fill in your keys
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend
npm install
npm run dev                                       # http://localhost:5173
```

## Sample data

`data/generate_sample_cvs.py` generates 16 synthetic candidate CVs (PDF) plus
`data/ground_truth.json` — the fixed test set used by the evaluation harness.

```bash
backend/.venv/Scripts/python data/generate_sample_cvs.py
```

<!-- Architecture diagram + metrics table land here in later phases -->
