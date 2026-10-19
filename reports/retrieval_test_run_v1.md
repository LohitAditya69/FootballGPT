# Retrieval test run v1

Run date: 2026-10-19. This was a verification/evaluation pass only; no
retrieval settings were tuned or changed during the run. The v1 and v2 held-out
sets were evaluated once and were not fed back into development selection.

The workbook-based prototype scorecard is now the primary day-to-day
development view. The v1/v2 benchmarks remain frozen archives for regression
and final evaluation; their test labels must not be used for tuning.

## Results

### Locked v1 UEFA pilot

The frozen 12-question pilot ran successfully: 10 questions had conditional
UEFA page qrels and 2 were not covered. The frozen selected BM25+G ranking
scored P@5 0.120, Recall@5 0.111, and MRR 0.267. Fixed BM25 scored
0.140/0.122/0.300. Same-match exclusion passed for all 12 historical queries.
These are low pilot scores and show that the selected development setting did
not transfer well to v1. No retuning was done on these questions.

Detailed output: `retrieval_evaluation.md` and
`retrieval_evaluation_per_question.csv`.

### Locked v2 held-out benchmark

The frozen 20-question held-out run completed. The development-selected BM25+G
setting scored P@5 0.080, Recall@5 0.400, and MRR 0.292. Fixed BM25 scored
0.090/0.450/0.275. The selected setting has a small MRR edge but lower P@5 and
recall, so the result is mixed rather than a clear overall improvement. The
held-out questions were not used to retune.

Detailed output: `retrieval_v2_heldout_evaluation.md` and
`retrieval_v2_heldout_per_question.csv`.

### Development comparison and prototype workbook labels

The 42-question dense/BM25/graph comparison was regenerated from the current
retriever implementation. On the existing AI-assisted qrels, fixed BM25 scored
0.171/0.619/0.612 for P@5/Recall@5/MRR; current BM25+G scored
0.181/0.655/0.632; dense-only scored 0.081/0.321/0.259. The workbook-derived
prototype rescoring was then refreshed. On its scripted labels, current
BM25+G scored direct-support P@5 0.352, Recall@5 0.542, MRR 0.617, and nDCG@5
0.801; fixed BM25 scored 0.324/0.503/0.629/0.788. BM25+G is higher on
precision, recall, and nDCG, while fixed BM25 is higher on MRR.

Both development views are provisional. The workbook uses scripted reviewer
profiles, and its candidate pages were drawn from retrieval outputs. Neither
view establishes independent human/coach judgment or complete qrels. Keep the
production retrieval configuration unchanged.

Detailed outputs: `dense_retrieval_development_comparison.md`,
`retrieval_workbook_review_evaluation_v1.md`, and their per-question CSVs.

### Historical retrieval H proxy

The match-disjoint H development run completed on 334 held-aside matches and a
75,175-case reference pool. For 3/10/25 situations per candidate match,
P@5 was 0.994/0.999/1.000, Recall@5 was 0.010/0.013/0.014, MRR@5 was 1.000
for all three, and nDCG@5 was 0.898/0.952/0.978. The evaluator enforces
candidate/query match separation.

These metrics are not a meaningful tactical retrieval benchmark: relevance is
defined from event type, play pattern, and location metadata, which overlaps
the ranker's input fields. The near-perfect top-rank results are therefore
self-confirming. Treat this as an implementation/leakage diagnostic only, not
evidence that H retrieves tactically similar real match situations. Outputs
remain outside the repository at `/private/tmp/footballgpt_historical_evaluation_v1/`.

## Final API/backend convergence rerun

The API previously hard-coded a 0.70/0.30 BM25/graph fusion, while the checked
in development-selected configuration specified 0.90/0.10. The API now loads
`ranking_config.json`, checks its BM25 `k1`/`b` against the built index,
normalizes both tactical channels using the shared retrieval normalizer, and
uses the configured relative V:G weights. Graph-only matches no longer qualify
as sufficient answer support without lexical grounding; this prevents broad
concept aliases such as “possession” from turning an unrelated passage into an
answer.

The API test suite passes: 13 passed, 2 dependency deprecation warnings. The
project `.venv` still lacks FastAPI, Pydantic, pytest, and NetworkX in a single
interpreter. Tests were run with Python 3.13 and the existing pure-Python
NetworkX 3.7 package on the local Python 3.14 environment path; no dependencies
were installed and no network access was needed. `py_compile` and
`git diff --check` also pass.

The current backend was run across all 42 workbook development questions. Its
top-3 output scored direct P@3 0.413, direct Recall@3 0.382, direct MRR 0.595,
nDCG@3 0.783, and Judged@3 0.968. It answered all 42, including seven with no
grade-2 workbook page, so these retrieval metrics do not validate answerability
or safe abstention. The labels remain provisional and retrieval-pool-limited.
See `retrieval_backend_workbook_evaluation_v1.md` for per-question results and
`retrieval_workbook_label_audit_v1.md` for the two reviewed direct-support
labels.
