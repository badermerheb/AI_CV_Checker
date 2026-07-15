# Retrieval configuration comparison

Gold set: 30 hand-verified questions over 16 fixed sample CVs.

| config | hit@5 | section-hit@5 | recall@5 | MRR | faithfulness | relevancy | p50 ms |
|---|---|---|---|---|---|---|---|
| baseline | 97% | 83% | 97% | 0.90 | 0.94 | 0.79 | 2629 |
| hybrid | 100% | 100% | 97% | 0.95 | — | — | — |
| hybrid_rerank | 100% | 100% | 98% | 0.98 | — | — | — |
| full | 100% | 100% | 100% | 0.98 | 0.89 | 0.89 | 3470 |

Metrics: hit@5 / recall@5 / MRR against hand-labelled expected sources; faithfulness + response relevancy via RAGAS (Gemini judge); latency is end-to-end chat p50.
