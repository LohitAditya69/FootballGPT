# Retrieval development evaluation

Development set: 42 AI-drafted, page-labeled questions over pages outside v1 and v2 held-out qrels. Labels are target-page annotations from the fixed report text; they are not human coach judgments.

## Baseline and selected development metrics

| Method | P@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| TF-IDF | 0.119 | 0.595 | 0.428 |
| BM25 (k1=1.5, b=0.75) | 0.124 | 0.619 | 0.523 |
| Selected BM25 + graph setting | 0.133 | 0.667 | 0.554 |

## Selected parameters

- BM25 `k1=0.8`, `b=0.5`; graph weight `β=0.1` with lexical weight `1−β`.
- Selection criterion fixed before tuning: maximize development MRR, then Recall@5, then P@5; ties prefer less graph contribution and values nearer the conventional BM25 baseline.
- Grid searched 80 combinations over `k1=(0.8, 1.2, 1.5, 2.0)`, `b=(0.25, 0.5, 0.75, 1.0)`, and graph weights `(0.0, 0.1, 0.2, 0.3, 0.5)`.
- This is development-only tuning. Neither v1's 12 questions nor the 20 v2 held-out questions were used to select parameters.

## Limitations

- Queries were drafted from the fixed reports and annotated with a target page; this is not independent human relevance adjudication and may favor report-specific phrasing.
- Each item has one target page, although other pages may be relevant. The labels are useful for controlled development but incomplete.
- On the new v2 held-out set, the selected setting has slightly higher MRR than fixed BM25 (0.292 vs 0.275) but lower P@5 and Recall@5 (0.080/0.400 vs 0.090/0.450); this is not a clear overall gain. Do not tune on v2 held-out questions.

Per-question ranks are in `retrieval_development_per_question.csv`.
