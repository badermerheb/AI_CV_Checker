# Evaluation harness

Measures the RAG pipeline against a **hand-built gold set** — 30 questions over the 16
fixed sample CVs, each with a manually verified answer and the exact source file
(and, where it matters, the CV section) that contains the evidence. Because every
label was written and checked by hand against `data/ground_truth.json`, the ground
truth is trustworthy; nothing here is auto-generated.

## Running it

```bash
python eval/run_eval.py --config baseline            # retrieval metrics only (no LLM cost)
python eval/run_eval.py --config full --generation   # + answers + RAGAS scoring
python eval/run_eval.py --report                     # comparison table -> results/comparison.md
```

Configs: `baseline` (dense top-5), `hybrid` (+BM25 fusion), `hybrid_rerank`
(+cross-encoder), `full` (+intent routing with candidate filters and job-fit
aggregation) — the API serves `full`.

## Metrics, and why these

**Retrieval** (computed directly against hand labels — no LLM judge, so zero noise):

- `hit_rate@5` — did any chunk from the right CV make top-5? On a 16-CV corpus this
  saturates quickly (the baseline already scores ~97%), so it's kept only as a sanity
  floor.
- `section_hit@5` — did we retrieve the chunk that actually **contains the answer**
  (e.g. the *experience* section, not just any chunk of the right CV)? This is the
  discriminating retrieval metric on this corpus and the one the upgrades were
  measured by.
- `recall@5` — for multi-candidate questions ("who speaks French?"), what fraction of
  expected CVs made it in? Job-fit questions need aggregation, not top-k, to score
  well here.
- `MRR` — how high does the first correct source rank?

**Generation** (RAGAS, Gemini as LLM-judge — same lite model as the app, since Google
zeroed the free-tier quota of older models like gemini-2.0-flash):

- `faithfulness` — is every claim in the answer supported by the retrieved excerpts?
  This is the inverse-hallucination number, the one that matters most for a recruiter
  tool making claims about real people.
- `response relevancy` — does the answer actually address the question?

RAGAS's context precision/recall metrics were deliberately skipped: they estimate
retrieval quality with an LLM judge, and this harness has exact hand-labelled source
ground truth — `section_hit@5`/`recall@5` measure the same thing without judge noise.

**Ops**: end-to-end latency p50/p95 per config, and cost ($0 — local embeddings +
reranker, free-tier LLM).

## Findings log

- **Dense-only retrieval fails on keyword-anchored questions** (82.6% section-hit):
  "Where did Sarah work before TechFlow?" retrieves her summary/skills chunks but not
  the experience section containing "TechFlow" — BM25 in the hybrid config fixes
  exactly this class (100%).
- **A bare cross-encoder reranker made retrieval WORSE** (100% → 91.3% section-hit)
  before fixing: chunk text often lacks the candidate's name (it lives in metadata),
  so the reranker promoted *other candidates'* education/languages sections. Fix:
  prefix `candidate_name — section:` to the text the reranker scores. After the fix,
  reranking is strictly better (MRR 0.95 → 0.983).
- **Reranker model choice is a latency call**: BAAI/bge-reranker-base scores 20 pairs
  in ~5s on CPU; Xenova/ms-marco-MiniLM-L-6-v2 does it ~10x faster with equal top-5
  quality on this corpus. MiniLM is the default; `RERANK_MODEL` swaps it.
- **Job-fit ranking needs aggregation, not top-k**: plain retrieval biases toward
  whoever has the most matching chunks; grouping scores per candidate and ranking a
  shortlist brought multi-candidate recall@5 to 100%.
- **Better retrieval lifts relevancy, not faithfulness**: answer relevancy jumped
  0.79 → 0.89 with the full pipeline, but faithfulness dipped 0.94 → 0.89 — job-fit
  answers make comparative claims ("X fits best") that the judge scores as weakly
  grounded even when every underlying fact is cited. A ranking is an inference over
  excerpts, not a quote from them; that is inherent to the feature, not a retrieval
  regression.
- **Free-tier quota archaeology**: gemini-3.5-flash allows 20 requests/day;
  gemini-2.0-flash now has ZERO free quota; free-tier models reject
  `candidateCount > 1` (RAGAS relevancy needs `strictness=1`). Model choice on the
  free tier is a real engineering constraint, not a footnote.
