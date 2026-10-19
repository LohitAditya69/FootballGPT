# Backend-aligned workbook development evaluation

This run calls `TacticalService.ask()` for all 42 development questions, so it evaluates the current backend path: tactical-chunk filtering, quality/abstention gate, config-driven BM25/graph fusion, fixed-chunk citation validation, and the API top-3 output.

The workbook labels are provisional scripted profiles over a retrieval-generated candidate set. This is a development diagnostic, not human/coach review or exhaustive relevance evaluation. No v1/v2 held-out labels were used.

Questions: 42. API answered: 42; abstained: 0. Questions with no grade-2 workbook page: 7.

| Metric | Backend result |
|---|---:|
| direct_P@3 | 0.413 |
| direct_Recall@3 | 0.382 |
| direct_MRR | 0.595 |
| nDCG@3 | 0.783 |
| Judged@3 | 0.968 |

## Exploratory V:G weight sensitivity

The following one-factor sweep changes only the relative graph weight while calling the same backend path. These values use the same provisional qrels that the sweep is selecting against; do not treat the best row as an independent result or automatically promote it.

| Graph weight (G) | Direct P@3 | Direct Recall@3 | Direct MRR | nDCG@3 | Judged@3 |
|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.429 | 0.392 | 0.595 | 0.790 | 0.968 |
| 0.10 | 0.413 | 0.382 | 0.595 | 0.783 | 0.968 |
| 0.20 | 0.429 | 0.397 | 0.591 | 0.777 | 0.952 |
| 0.30 | 0.405 | 0.379 | 0.591 | 0.754 | 0.921 |

In this same-label sensitivity sweep, BM25-only (G=0) is slightly higher than the configured G=0.10 setting on P@3, Recall@3, and nDCG@3, and ties MRR and judged coverage. This is an exploratory candidate, not a promotion: the qrels are scripted, retrieval-generated, and reused to select the candidate.

Because the workbook qrels come from a retrieval-generated pool and seven questions have no grade-2 page, answer/abstention status is reported separately and these metrics must not be read as proof of factual answerability.

Per-question results are in `retrieval_backend_workbook_evaluation_v1.csv`; weight sensitivity values are in `retrieval_backend_fusion_sweep_v1.csv`.
