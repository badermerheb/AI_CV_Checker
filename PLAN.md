# AI CV Checker — Project Plan
> Project 1 from the AI Engineer Roadmap: Production-Grade RAG App with Evaluation.
> Recruiters upload CVs/resumes, then chat: "Who best fits this job?", "Tell me about candidate X", or general questions across all CVs.

## Success criteria (from the roadmap PDF)
- [ ] Document upload + ingestion pipeline (parse → chunk → embed → index)
- [ ] Hybrid retrieval (vector + keyword) with a reranking step
- [ ] Answers with inline citations back to source CV chunks
- [ ] Evaluation harness + report: retrieval hit-rate, faithfulness, latency, cost
- [ ] Dockerized, deployed, publicly reachable
- [ ] README with architecture diagram + metrics table (before/after reranking)
- [ ] Showcase: live demo link, before/after eval table, 60-second demo GIF

## Architecture

```
React (Vite + TS)  ──REST──►  FastAPI + LlamaIndex
   Upload page                  │
   Candidates page              ├─ INGEST  /upload
   Chat page (citations)        │    parse PDF/DOCX → chunk → extract profile JSON (LLM)
                                │    → dense embed (BGE) + sparse (BM25) → Qdrant
                                │
                                ├─ CHAT    /chat
                                │    intent routing → hybrid retrieve → rerank (bge-reranker)
                                │    → LLM (Gemini) → answer + citations
                                │
                                ├─ Langfuse tracing on every request
                                │
                                └─ EVAL    scripts/run_eval.py
                                     gold set (JSONL) → RAGAS + hit-rate/MRR → report
Qdrant  ── runs in Podman container (dev) / Qdrant Cloud free tier (prod)
```

## Stack decisions (and why)

| Component | Choice | Why |
|---|---|---|
| Frontend | React + Vite + TypeScript | Your choice; Vite is the fastest setup, deploys free on Vercel |
| Backend | FastAPI + LlamaIndex | Your choice; LlamaIndex has first-class Qdrant hybrid + reranker + Langfuse integrations |
| Embeddings | **BAAI/bge-small-en-v1.5** via FastEmbed (ONNX) | Top-tier quality-per-CPU-millisecond, 384-dim, runs free/local, light enough for free-tier hosting. If CVs may be French/Arabic, switch to `BAAI/bge-m3` (multilingual) |
| Sparse/keyword | Qdrant BM25 (via FastEmbed sparse) | Gives the "hybrid" requirement with `enable_hybrid=True` in LlamaIndex's QdrantVectorStore — no separate keyword engine needed |
| Reranker | BAAI/bge-reranker-v2-m3 (local cross-encoder) | The roadmap's pick; big precision win, free, CPU-friendly at top-20 candidates |
| Vector DB | Qdrant in **Podman** (dev), Qdrant Cloud free 1GB (deployed demo) | Qdrant is one container — Podman handles it identically to Docker (`podman run`). No reason to learn Docker for this; the deploy Dockerfile builds fine with `podman build` too |
| LLM | Gemini free tier (`gemini-2.5-flash`) | Free, available in Lebanon (Groq is not), strong at citation-following and JSON extraction, native function calling. Fallbacks: OpenRouter free models (works anywhere with just an API key) or Ollama (fully local/offline) |
| Eval | RAGAS + hand-built gold set | See "Evaluation plan" below |
| Tracing | Langfuse Cloud free tier | See "What Langfuse is for" below |
| Deploy | Backend → Hugging Face Spaces or Render (free); Frontend → Vercel (free) | All $0 |

## CV-specific design (the part that makes this better than generic RAG)

**1. Per-candidate metadata.** Every chunk carries payload: `candidate_id`, `candidate_name`, `filename`, `section`. This enables:
- "Tell me about Sarah" → metadata **filter** to Sarah's chunks only (no cross-candidate contamination)
- Clean citations: "(Sarah_CV.pdf, Experience section)"

**2. Structured profile extraction at ingest.** One LLM call per CV extracts JSON: `{name, current_title, years_experience, skills[], education[], languages[]}`. Stored alongside chunks. Powers the candidate list UI and makes comparisons reliable.

**3. Query routing (3 intents).** A small LLM classification step (or function calling) routes each question:
- **Single-candidate Q&A** → filtered retrieval on that candidate
- **Job-fit ranking** ("who best fits this JD?") → see below
- **General/cross-CV chat** → unfiltered hybrid retrieval

**4. Job-fit ranking is aggregation, not plain RAG.** Naive top-k retrieval biases toward whoever has the most matching chunks. Instead:
1. Hybrid-retrieve top ~50 chunks across all candidates against the job description
2. Aggregate score per candidate (mean of their top-3 chunk scores)
3. Take top ~5 candidates → feed their profile JSONs + best chunks + the JD to the LLM
4. LLM returns a ranked shortlist with per-candidate justification and citations

This design decision is a great README/interview talking point.

**5. Chunking.** CVs are short (1–2 pages). Split by section headers when detectable (Experience, Education, Skills…), else sentence-window ~512 tokens with small overlap. Section name goes into metadata.

## Phases

### Phase 0 — Setup (~half a day)
- `ai-cv-checker/` repo: `backend/` (uv or venv, FastAPI skeleton), `frontend/` (Vite React TS), `eval/`, `README.md`. Git init + GitHub repo.
- Qdrant via Podman: `podman run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant` → dashboard at http://localhost:6333/dashboard
- Accounts: Gemini API key (aistudio.google.com — free, no card needed), Langfuse Cloud project (cloud.langfuse.com) → `.env` with `GOOGLE_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `QDRANT_URL`. If Gemini is ever blocked, an OpenRouter key is a drop-in replacement.
- **Test data**: 15–20 sample CVs (PDF), varied roles/seniority. Generate synthetic ones or use a public resume dataset. Fixed test set = reproducible evals.
- **Done when:** Qdrant dashboard loads, FastAPI `/health` returns 200, keys work.

### Phase 1 — Ingestion pipeline (~1 day)
- `POST /upload`: accept PDF/DOCX → parse (PyMuPDF / docx2txt) → chunk → profile-extraction LLM call → index into Qdrant (dense BGE + sparse BM25, `enable_hybrid=True`)
- `GET /candidates`: list extracted profiles
- **Done when:** all sample CVs ingested; Qdrant dashboard shows chunks with correct payloads; profiles look right.

### Phase 2 — Chat v1: naive RAG + citations + tracing (~1 day)
- `POST /chat`: dense-only top-5 retrieval → Gemini answer, prompt forces inline citations `[1]`, `[2]` mapped to source chunks returned in the response
- Conversation memory (last N turns in the prompt; session id per chat)
- Wire **Langfuse** now (LlamaIndex instrumentation + FastAPI middleware) — you'll use the traces to debug everything after this point
- **Done when:** curl a question, get a cited answer; the full trace (retrieval → LLM) is visible in Langfuse.

### Phase 3 — Gold set + eval harness → BASELINE numbers (~1 day)
- Write the gold set: 25–40 questions over the fixed sample CVs (see format below), covering all 3 intents
- `eval/run_eval.py`: runs every gold question through the pipeline → RAGAS (faithfulness, answer relevancy, context precision/recall) + custom hit-rate@5 and MRR + latency → markdown report
- **Done when:** you have a baseline metrics table committed. Don't skip this — the before/after story needs the "before."

### Phase 4 — Retrieval upgrades → AFTER numbers (~1–2 days)
- Switch retrieval to hybrid (dense + BM25, RRF fusion) → re-run eval
- Add bge-reranker: retrieve top-20 → rerank → keep top-5 → re-run eval
- Add intent routing + candidate filters + job-fit aggregation (design above) → re-run eval
- **Done when:** metrics table shows each step's impact, e.g. "hit-rate 71% → 89%". This table is the centerpiece of the README.

### Phase 5 — React frontend (~2 days)
- **Upload page**: drag-and-drop multi-file, ingestion progress, candidate cards appear from profile JSON
- **Chat page**: message list, input, citation chips ([1], [2]) that expand the source chunk + candidate name
- **Candidates page**: profile list + detail view
- Simple clean styling (Tailwind). Streaming responses optional polish.
- **Done when:** full flow works locally end-to-end in the browser.

### Phase 6 — Ship it (~1 day)
- `Dockerfile` for backend (build with `podman build`)
- Prod Qdrant: Qdrant Cloud free 1GB cluster (just change `QDRANT_URL` + API key)
- Deploy backend to HF Spaces or Render (free), frontend to Vercel; CORS + env vars
- README: what it does, architecture diagram, metrics table, how to run; record 60-second demo GIF
- **Done when:** a stranger can open the URL, upload a CV, and chat with citations.

**Total: roughly 7–9 working days.**

## Evaluation plan (RAGAS + gold set explained)

**What a "hand-built gold set" is:** a small evaluation dataset you write yourself, so the ground truth is trustworthy. For a fixed set of sample CVs, each row is:

```json
{"question": "How many years of Python experience does Sarah Chen have?",
 "ground_truth": "5 years, at DataCorp (2019-2022) and TechFlow (2022-2024)",
 "expected_source": "sarah_chen.pdf",
 "intent": "single_candidate"}
```

~25–40 rows across the three intents (single-candidate facts, comparisons, job-fit). "Hand-built" just means you wrote and verified each answer manually instead of auto-generating them — it's your exam answer key.

**What gets measured on every eval run:**
- **Retrieval**: hit-rate@5 (did the expected CV's chunks get retrieved?), MRR — computed directly against `expected_source`
- **Generation (RAGAS)**: faithfulness (is the answer supported by retrieved chunks? ≈ inverse hallucination rate), answer relevancy, context precision/recall — RAGAS uses an LLM-as-judge (Gemini free tier works)
- **Ops**: p50/p95 latency, token counts, cost ($0 — say it anyway)

## What Langfuse is for

Langfuse records a **trace** of every request through your pipeline: the user's question, which chunks retrieval returned and their scores, what the reranker did, the exact prompt sent to Gemini, the answer, plus latency and token counts for each step — shown as a waterfall in a web dashboard.

You'll use it to: debug bad answers (9 times out of 10 the retrieval was wrong, and the trace shows it instantly), spot latency bottlenecks, and demo "observability" in interviews — it's the roadmap's "prove it works in production" ingredient. Free cloud tier at cloud.langfuse.com; LlamaIndex integrates with a few lines.

## Risks / notes
- **Gemini free-tier rate limits**: a per-minute and per-day request cap applies on the free tier — fine for dev/demo, but eval runs over the full gold set need throttling (sleep between calls) or batching across a couple of runs.
- **Free hosting cold starts**: Render/HF Spaces sleep when idle — mention in README so demo visitors aren't surprised.
- **PDF parsing variance**: some CVs have weird layouts (columns, tables). PyMuPDF handles most; keep 1–2 ugly CVs in the test set on purpose.
- **Reranker on CPU**: only rerank top-20, not top-50, to keep latency reasonable.
