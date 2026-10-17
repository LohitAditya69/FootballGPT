# Retrieval benchmark v2: held-out results

This is the 20-question v2 test split. Its target pages do not overlap v1 qrels, v2 development pages, or the earlier 22-question development set. The v2 questions and pages were not used for parameter selection.

## Results

| Method | P@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| TF-IDF | 0.090 | 0.450 | 0.283 |
| BM25 (k1=1.5, b=0.75) | 0.090 | 0.450 | 0.275 |
| Frozen development-selected BM25+G | 0.080 | 0.400 | 0.292 |

Metrics rank distinct report pages by their best chunk score. Each question has one target page. `P@5` divides by five; `Recall@5` is hit/no-hit because each item has one target page; MRR is reciprocal rank of that page.

## Limits

Questions and target-page labels were AI-drafted from the fixed reports, not independently judged by human coaches. Other pages may also be relevant, so the single-page labels are incomplete. The set is page-disjoint from development and v1 but remains a small pilot; do not tune against it.

Per-question results: `retrieval_v2_heldout_per_question.csv`.
