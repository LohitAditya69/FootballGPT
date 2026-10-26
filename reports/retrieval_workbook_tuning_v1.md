# Provisional workbook-based BM25/graph tuning sweep

This is a development-only, exploratory sweep over the 42 workbook questions. It did not read v1 or v2 held-out labels and did not modify `backend/retrieval/ranking_config.json`.

The workbook qrels are independent human coach judgments over a retrieval-generated, non-exhaustive candidate pool. Results are candidate-pool diagnostics, not exhaustive corpus validation. The tuning grid reuses those labels, so the highest score is subject to selection bias and must not be treated as a reliable generalization estimate.

Search space: 128 combinations; `k1=(0.8, 1.2, 1.5, 2.0)`, `b=(0.25, 0.5, 0.75, 1.0)`, graph weights `(0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5)`. Objective ordering for this exploratory report: nDCG@5 (grade 2 gain 3, grade 1 gain 1), then direct-support P@5, direct-support MRR, direct-support recall, then lower graph weight.

## Current serving setting vs exploratory top candidate

| Setting | k1 | b | graph weight | direct P@5 | direct Recall@5 | direct MRR | nDCG@5 | Judged@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Current serving config | 0.8 | 0.5 | 0.10 | 0.352 | 0.542 | 0.617 | 0.801 | 0.967 |
| Top exploratory candidate | 1.5 | 0.25 | 0.00 | 0.352 | 0.526 | 0.643 | 0.808 | 0.967 |

The top candidate is BM25-only (`k1=1.5`, `b=0.25`, graph weight 0). Against the current setting it ties direct P@5, improves direct MRR and nDCG@5 slightly, and lowers direct recall. No candidate is a consistent improvement across all metrics; do not promote it to serving config from this sweep.

The next refinement should improve the judgment set or test a separately specified retrieval change with independent review. In a spot audit, the workbook marked UEFA Europa Conference League 2024/25 page 30 as direct support for a question about centre-backs defending large spaces in a high line, but the quoted text discusses Chelsea full-backs leaving teammates 1v1. This is a concrete example of why the current metrics are diagnostic only.

All 128 grid results are in `retrieval_workbook_tuning_v1.csv`.

## Candidate-pool depth diagnostic

The following sweep holds BM25 parameters and BM25/graph weights at the current serving settings, varying only the number of candidates retrieved per channel before page fusion. It reuses the same provisional workbook labels and is therefore diagnostic, not an independent estimate.

| Candidates per channel | direct P@5 | direct Recall@5 | direct MRR | nDCG@5 | Judged@5 |
|---:|---:|---:|---:|---:|---:|
| 20 | 0.352 | 0.542 | 0.617 | 0.801 | 0.967 |
| 40 | 0.357 | 0.545 | 0.617 | 0.800 | 0.962 |
| 60 | 0.362 | 0.569 | 0.608 | 0.800 | 0.962 |
| 100 | 0.371 | 0.580 | 0.610 | 0.801 | 0.957 |
| 150 | 0.357 | 0.549 | 0.613 | 0.795 | 0.952 |
| 200 | 0.357 | 0.544 | 0.617 | 0.802 | 0.962 |

A wider candidate pool can increase direct hits and recall, but the gain is small and nDCG is essentially flat; judged coverage also drops because more unjudged pages enter the ranking. Do not increase production depth from these labels alone. The per-depth values are in `retrieval_workbook_candidate_pool_v1.csv`.
