# Retrieval development evaluation

The workbook-based scorecard in `retrieval_workbook_review_evaluation_v1.md`
is now the primary day-to-day prototype evaluation. This earlier AI-qrel
development comparison is retained as a supporting baseline; the v1/v2 sets
remain frozen archived holdouts.

Development set: 42 AI-drafted questions with source-qualified, multi-page qrels outside v1 and v2 held-out qrels. Labels are AI-assisted candidate-page judgments from the fixed report text; they are incomplete and not human coach judgments.

P@5 counts relevant pages in the top five divided by five; Recall@5 counts retrieved relevant pages divided by all labeled relevant pages; MRR uses the first relevant page.

## Baseline and selected development metrics

| Method | P@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| TF-IDF | 0.162 | 0.583 | 0.521 |
| BM25 (k1=1.5, b=0.75) | 0.171 | 0.619 | 0.612 |
| Selected BM25 + graph setting | 0.181 | 0.655 | 0.634 |

## Selected parameters

- BM25 `k1=1.5`, `b=0.25`; graph weight `β=0.2` with lexical weight `1−β`.
- Selection criterion fixed before tuning: maximize development MRR, then Recall@5, then P@5; ties prefer less graph contribution and values nearer the conventional BM25 baseline.
- Grid searched 80 combinations over `k1=(0.8, 1.2, 1.5, 2.0)`, `b=(0.25, 0.5, 0.75, 1.0)`, and graph weights `(0.0, 0.1, 0.2, 0.3, 0.5)`.
- This is development-only tuning. Neither v1's 12 questions nor the 20 v2 held-out questions were used to select parameters.

## Limitations

- Labels are AI-assisted candidate-page judgments, not exhaustive page-by-page adjudication and not coach review; omitted relevant pages remain possible.
- The original target page remains relevant. Additional pages were included only when their report text directly addresses the question; retrieval rank alone is not a relevance judgment.
- On the v2 held-out set, selected BM25+G has slightly higher MRR than fixed BM25 but lower P@5 and Recall@5; this is not a clear overall gain. Do not tune against v2 held-out questions.

Per-question ranks and qrel provenance are in `retrieval_development_per_question.csv`.

## Human review and semantic retrieval status

The current multi-page qrels are still AI-assisted and incomplete. A blinded
review packet containing 1,071 development question-page candidates, full page
text, and blank judgment fields is available at
`retrieval_human_review_packet_v1.csv`. It draws candidates from TF-IDF,
fixed BM25, graph retrieval, and existing labels; it is not an exhaustive
review of all pages. Reviewers must add relevant pages missed by the candidate
pool. The rating rubric, independent-review procedure, adjudication, and
agreement reporting requirements are in `retrieval_human_review_protocol.md`.

Dense retrieval was evaluated after the local runtime became available. See
`dense_retrieval_development_comparison.md` for the development-only comparison
of BM25, MiniLM dense retrieval, three BM25+dense fusion weights, and the
current BM25+graph baseline. Dense-only retrieval trailed fixed BM25 on the
current qrels; the 25%-dense hybrid was close to BM25. The qrels are still
AI-assisted and incomplete, so no production setting was changed. The runtime
versions are listed in `requirements-embedding.txt`; the cached model revision
is pinned in the comparison report. Complete the human review before treating
small metric differences as evidence of improvement.

### Prototype workbook rescore

The user-provided `retrieval_review_v1.xlsx` was incorporated as a separate
provisional label view, without changing the workbook or replacing the
AI-qrel baseline above. Its 1,071 labels span 42 questions: 134 direct (2),
735 partial (1), 202 uncertain, and no adjudicated grade 0. The workbook uses
independent human coach reviewers, as confirmed by the user. The
exported qrels omit full page text and excerpts. Current rankings were
rescored in `retrieval_workbook_review_evaluation_v1.md`; grade 2 is the
strict direct-support relevance definition, grade 1 is retained for a graded
and inclusive sensitivity view, and uncertain pages are excluded. These
candidate-pool metrics remain provisional and are not reliability or factuality
evidence. Keep production retrieval unchanged.
