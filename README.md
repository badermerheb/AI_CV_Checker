---
title: AI CV Checker
emoji: ✅
colorFrom: green
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
---

# AI CV Checker

**Live demo: https://ai-cv-checker-e621.onrender.com** *(free tier — first request
after idle takes ~1 min to wake)*

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
                                 └─ Postgres (Neon): profiles + chat sessions
                                    (SQLite fallback when DATABASE_URL is unset)
Qdrant in Podman (dev) / Qdrant Cloud (prod)

Multi-user isolation without logins: each browser gets an anonymous workspace id
(localStorage → X-Workspace-Id header). Uploads are tagged with it in Qdrant payloads
and Postgres rows; every query filters to your workspace + the shared read-only demo
corpus. Other visitors never see your uploads.
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
hit-rate saturates at ~97-100% on a corpus this size).

Generation quality (RAGAS, Gemini judge, 30 answered questions per config):

| config | faithfulness | answer relevancy | latency p50 |
|---|---|---|---|
| baseline | 0.94 | 0.79 | 2.6 s |
| full pipeline | 0.89 | **0.89** | 3.5 s |

Better retrieval lifts relevancy sharply (+0.10). The small faithfulness dip is the
job-fit ranking trade-off: comparative claims ("X fits best") are judged as weakly
grounded even when each underlying fact is cited. Per-question detail in
[eval/results/](eval/results/).

## Run with one container

```bash
podman build -t cv-checker .        # docker works identically
podman run --rm -p 8080:8000 --env-file backend/.env \
  -e QDRANT_URL=http://host.containers.internal:6333 cv-checker
# open http://localhost:8080 — UI + API from a single container
```

Deploying to a public URL (Render / HF Spaces / Qdrant Cloud, all free): see
[DEPLOY.md](DEPLOY.md).

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
