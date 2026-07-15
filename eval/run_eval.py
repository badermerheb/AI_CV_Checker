"""Evaluation harness for the CV Checker RAG pipeline.

Retrieval metrics (no LLM needed for scoring): hit-rate@5, recall@5, MRR — computed
against the hand-verified expected_sources in gold_set.jsonl.
Generation metrics (--generation): answers each gold question through the full chat
pipeline, then scores with RAGAS (faithfulness, response relevancy) using a Gemini
judge on a separate free-tier quota bucket.

Usage:
  python eval/run_eval.py --config baseline
  python eval/run_eval.py --config full --generation
  python eval/run_eval.py --report          # comparison table from saved results
"""

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND = EVAL_DIR.parent / "backend"
RESULTS = EVAL_DIR / "results"

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)  # so app.config finds backend/.env

CONFIGS: dict[str, dict] = {
    "baseline": {"mode": "dense", "rerank": False, "routing": False},
    "hybrid": {"mode": "hybrid", "rerank": False, "routing": False},
    "hybrid_rerank": {"mode": "hybrid", "rerank": True, "routing": False},
    "full": {"mode": "hybrid", "rerank": True, "routing": True},
}


def load_gold(limit: int | None) -> list[dict]:
    rows = [json.loads(line) for line in (EVAL_DIR / "gold_set.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit] if limit else rows


def eval_retrieval(gold: list[dict], config: dict) -> dict:
    from app.chat import gather_context

    per_question = []
    for row in gold:
        t0 = time.perf_counter()
        nodes, _, decision = gather_context(row["question"], [], **config)
        latency = time.perf_counter() - t0
        retrieved = [n.node.metadata.get("filename") for n in nodes]
        retrieved_sections = [
            f"{n.node.metadata.get('filename')}#{n.node.metadata.get('section') or ''}" for n in nodes
        ]
        expected = set(row["expected_sources"])

        hit = any(f in expected for f in retrieved)
        recall = len(expected & set(retrieved)) / len(expected)
        rank = next((i + 1 for i, f in enumerate(retrieved) if f in expected), None)
        # Section-level hit: did we retrieve a chunk that actually CONTAINS the answer?
        # File-level hit saturates on a small corpus; this is the discriminating metric.
        section_hit = (
            any(s in set(row["expected_sections"]) for s in retrieved_sections)
            if "expected_sections" in row
            else None
        )
        per_question.append(
            {
                "id": row["id"],
                "intent": row["intent"],
                "hit": hit,
                "recall": recall,
                "rr": 1 / rank if rank else 0.0,
                "section_hit": section_hit,
                "latency_s": round(latency, 3),
                "routed_intent": decision.intent,
                "retrieved": retrieved_sections,
            }
        )
        s_flag = {True: "Y", False: "n", None: "-"}[section_hit]
        print(
            f"  q{row['id']:>2} [{row['intent']:>16}] hit={'Y' if hit else 'n'} section_hit={s_flag} recall={recall:.2f}",
            flush=True,
        )

    n = len(per_question)
    with_sections = [q for q in per_question if q["section_hit"] is not None]
    summary = {
        "hit_rate@5": round(sum(q["hit"] for q in per_question) / n, 4),
        "section_hit@5": round(sum(q["section_hit"] for q in with_sections) / len(with_sections), 4)
        if with_sections
        else None,
        "recall@5": round(sum(q["recall"] for q in per_question) / n, 4),
        "mrr": round(sum(q["rr"] for q in per_question) / n, 4),
        "retrieval_p50_s": round(statistics.median(q["latency_s"] for q in per_question), 3),
    }
    return {"summary": summary, "per_question": per_question}


def eval_generation(gold: list[dict], config: dict, config_name: str) -> dict:
    from app.chat import chat

    samples, latencies = [], []
    for row in gold:
        result = chat(row["question"], session_id=f"eval-{config_name}-{row['id']}", **config)
        latencies.append(result["latency_ms"])
        samples.append(
            {
                "user_input": row["question"],
                "response": result["answer"],
                # Label each context the way the LLM actually sees it in the prompt
                # ("[n] Name — section"): bare chunk text often lacks the candidate's
                # name, which makes the faithfulness judge (rightly) refuse attribution.
                "retrieved_contexts": [
                    f"{c['candidate_name']} — {c['section'] or 'CV'}: {c['snippet']}"
                    for c in result["citations"]
                ],
                "reference": row["ground_truth"],
            }
        )
        print(f"  q{row['id']:>2} answered in {result['latency_ms']}ms", flush=True)
        time.sleep(2)  # stay under free-tier RPM

    ragas_scores = run_ragas(samples)
    return {
        "ragas": ragas_scores,
        "latency_ms_p50": int(statistics.median(latencies)),
        "latency_ms_p95": int(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]),
        "samples": samples,
    }


def run_ragas(samples: list[dict]) -> dict:
    from app.config import settings
    from langchain_community.embeddings import FastEmbedEmbeddings
    from langchain_google_genai import ChatGoogleGenerativeAI
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, ResponseRelevancy

    judge = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model=settings.ragas_judge_model,
            temperature=0,
            google_api_key=settings.google_api_key,
            transport="rest",  # async gRPC can hang under ragas's event loop on Windows
        )
    )
    embeddings = LangchainEmbeddingsWrapper(FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5"))
    dataset = EvaluationDataset.from_list(samples)
    result = evaluate(
        dataset,
        metrics=[Faithfulness(), ResponseRelevancy()],
        llm=judge,
        embeddings=embeddings,
        # generous timeout: free-tier 429s carry ~45s retry delays
        run_config=RunConfig(max_workers=1, timeout=600),
    )
    frame = result.to_pandas()
    scores = {}
    for col in frame.columns:
        if col in ("faithfulness", "answer_relevancy", "response_relevancy"):
            scores[col] = round(float(frame[col].mean()), 4)
    return scores


def report() -> None:
    rows = []
    for name in CONFIGS:
        path = RESULTS / f"{name}.json"
        if path.exists():
            rows.append((name, json.loads(path.read_text(encoding="utf-8"))))
    if not rows:
        print("no saved results yet")
        return

    headers = ["config", "hit@5", "section-hit@5", "recall@5", "MRR", "faithfulness", "relevancy", "p50 ms"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for name, data in rows:
        s = data["retrieval"]["summary"]
        g = data.get("generation") or {}
        ragas = g.get("ragas") or {}
        relevancy = ragas.get("answer_relevancy", ragas.get("response_relevancy"))
        lines.append(
            "| {} | {:.0%} | {} | {:.0%} | {:.2f} | {} | {} | {} |".format(
                name,
                s["hit_rate@5"],
                f"{s['section_hit@5']:.0%}" if s.get("section_hit@5") is not None else "—",
                s["recall@5"],
                s["mrr"],
                f"{ragas['faithfulness']:.2f}" if "faithfulness" in ragas else "—",
                f"{relevancy:.2f}" if relevancy is not None else "—",
                g.get("latency_ms_p50", "—"),
            )
        )
    table = "\n".join(lines)
    print(table)
    (RESULTS / "comparison.md").write_text(
        "# Retrieval configuration comparison\n\n"
        f"Gold set: {len(load_gold(None))} hand-verified questions over 16 fixed sample CVs.\n\n"
        + table
        + "\n\nMetrics: hit@5 / recall@5 / MRR against hand-labelled expected sources; "
        "faithfulness + response relevancy via RAGAS (Gemini judge); latency is end-to-end chat p50.\n",
        encoding="utf-8",
    )
    print(f"\nwrote {RESULTS / 'comparison.md'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=list(CONFIGS), default=None)
    parser.add_argument("--generation", action="store_true", help="also run answer + RAGAS eval")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report", action="store_true", help="print comparison table from saved results")
    args = parser.parse_args()

    if args.report:
        report()
        return
    if not args.config:
        parser.error("--config or --report required")

    RESULTS.mkdir(exist_ok=True)
    gold = load_gold(args.limit)
    config = CONFIGS[args.config]
    print(f"== {args.config} {config} on {len(gold)} questions")

    out_path = RESULTS / f"{args.config}.json"
    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

    print("-- retrieval metrics")
    retrieval = eval_retrieval(gold, config)
    print(json.dumps(retrieval["summary"], indent=2))

    generation = existing.get("generation")
    if args.generation:
        print("-- generation + RAGAS")
        generation = eval_generation(gold, config, args.config)
        print(json.dumps({k: v for k, v in generation.items() if k != "samples"}, indent=2))

    out_path.write_text(
        json.dumps({"config": config, "retrieval": retrieval, "generation": generation}, indent=2),
        encoding="utf-8",
    )
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
