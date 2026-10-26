# Retrieval evaluation using independent coach-reviewed judgments

## Scope and provenance

This rescored the existing top-five development rankings for 42 questions against 1,071 page judgments exported from the user's review workbook. The workbook was not modified. Reviewers 1A and 1B are independent human coaches, as confirmed by the user. The adjudicated labels are coach-reviewed page relevance judgments. The candidate pool was generated from retrieval and is non-exhaustive, so these results are not an exhaustive corpus evaluation or proof of factual correctness.

Adjudicated labels: 134 direct (grade 2), 735 partial (grade 1), 0 not relevant (grade 0), and 202 uncertain. Uncertain pages are excluded from graded gains and relevance denominators. The workbook's candidate pages are not exhaustive; unjudged pages in a returned top five count as misses in precision and are exposed via Judged@5, so these scores are conservative and candidate-pool dependent.

The stricter primary view treats only grade 2 as relevant. A sensitivity view treats grades 1 and 2 as relevant. nDCG@5 uses gain 3 for direct support and gain 1 for partial support. These definitions preserve the workbook rubric without collapsing partial support into direct support silently.

## Strict direct-support results

P@5 uses all five returned pages in the denominator. Recall@5 uses the judged direct-support pages per question. MRR is the reciprocal rank of the first direct-support page. Judged@5 is the fraction of returned pages assigned grade 0, 1, or 2 rather than uncertain or unjudged.

| Method | P@5 | Recall@5 | MRR | Judged@5 |
|---|---:|---:|---:|---:|
| Fixed BM25 | 0.324 | 0.503 | 0.629 | 0.967 |
| Dense MiniLM | 0.133 | 0.180 | 0.296 | 0.814 |
| BM25 + 25% dense | 0.314 | 0.475 | 0.596 | 0.952 |
| BM25 + 50% dense | 0.238 | 0.363 | 0.528 | 0.895 |
| BM25 + 75% dense | 0.143 | 0.210 | 0.323 | 0.814 |
| Current BM25 + graph baseline | 0.352 | 0.542 | 0.617 | 0.967 |

## Graded and inclusive sensitivity views

| Method | nDCG@5 (2>1>0) | P@5 (grades 1–2) | Recall@5 (grades 1–2) |
|---|---:|---:|---:|
| Fixed BM25 | 0.788 | 0.967 | 0.239 |
| Dense MiniLM | 0.536 | 0.814 | 0.200 |
| BM25 + 25% dense | 0.768 | 0.952 | 0.236 |
| BM25 + 50% dense | 0.679 | 0.895 | 0.222 |
| BM25 + 75% dense | 0.550 | 0.814 | 0.201 |
| Current BM25 + graph baseline | 0.801 | 0.967 | 0.239 |

## Paired outcomes vs fixed BM25

Better / tied / worse by question, under the strict direct-support view:

| Method | P@5 | Recall@5 | MRR | Judged@5 |
|---|---:|---:|---:|---:|
| Dense MiniLM | 3 / 12 / 27 | 3 / 12 / 27 | 3 / 17 / 22 | 1 / 19 / 22 |
| BM25 + 25% dense | 2 / 36 / 4 | 2 / 36 / 4 | 0 / 37 / 5 | 0 / 40 / 2 |
| BM25 + 50% dense | 2 / 22 / 18 | 2 / 22 / 18 | 2 / 28 / 12 | 0 / 29 / 13 |
| BM25 + 75% dense | 2 / 15 / 25 | 2 / 15 / 25 | 2 / 21 / 19 | 0 / 21 / 21 |
| Current BM25 + graph baseline | 9 / 30 / 3 | 9 / 30 / 3 | 4 / 34 / 4 | 0 / 42 / 0 |

## Interpretation and next action

These results show how current rankings align with independent coach judgments on the reviewed candidate pages; they do not establish factual correctness or exhaustive corpus recall. The candidate pool included retrieval-suggested pages and may omit relevant pages. Exact agreement was 937/1,071 (87.5%), including 202 pairs both marked uncertain; among the 869 pairs where both reviewers gave a categorical grade, exact agreement was 735/869 (84.6%). These are raw exact-agreement rates, not chance-corrected reliability statistics. Treat small differences as diagnostic only. Improve candidate-pool coverage and evaluate generated answers separately before changing serving behavior.

The prior AI-qrel comparison is preserved in `dense_retrieval_development_comparison.md`. This report is an additional workbook-label view, not a replacement for that baseline or a held-out evaluation. Per-question details and judged coverage are in `retrieval_workbook_review_evaluation_v1.csv`.
