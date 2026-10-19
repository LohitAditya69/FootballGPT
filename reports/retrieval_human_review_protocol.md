# Human review protocol for UEFA retrieval qrels

## Primary prototype evaluation workflow

The workbook-based scorecard is the project's primary day-to-day prototype
evaluation. Refresh its rankings and rescore with:

```bash
./.venv/bin/python scripts/compare_dense_retrieval_on_dev.py
./.venv/bin/python scripts/import_retrieval_review_workbook.py /path/to/retrieval_review_v1.xlsx
./.venv/bin/python scripts/evaluate_retrieval_workbook_review_v1.py
./.venv/bin/python scripts/tune_retrieval_on_workbook.py
./.venv/bin/python scripts/evaluate_backend_workbook_review.py
```

The import also needs `openpyxl` from `requirements-review.txt`. The workbook
is a prototype input with scripted reviewer profiles and a retrieval-generated
candidate pool; its metrics must not be described as human or coach review.
The exploratory tuner reports candidates but never changes the serving config;
do not promote a setting on a mixed result or from these provisional labels
alone. It also compares candidate-pool depths and writes
`reports/retrieval_workbook_candidate_pool_v1.csv`; interpret higher P@5 or
recall alongside nDCG and judged coverage, since this workbook only labels a
retrieval-generated subset of report pages.
The v1 and v2 question/qrel sets remain frozen archives for regression and
final evaluation, not active tuning sets. Do not delete or tune on them.

## Prototype workbook status

`retrieval_review_v1.xlsx` is being used as a prototype label source at the
user's direction. Its two reviewer profiles (`1A` and `1B`) are scripted
profiles, not independent human reviewers or coaches. Its grades can support
pipeline debugging and a provisional sensitivity analysis, but must not be
called human review, coach review, inter-rater reliability, or ground truth.
The workbook remains unchanged and outside the repository. The exported
`retrieval_workbook_review_qrels_v1.csv` contains only question/page IDs,
grades, and label provenance; it excludes the workbook's full page text and
quoted passages.

Regenerate that compact export and its separate ranking evaluation with:

```bash
./.venv/bin/pip install -r requirements-review.txt
./.venv/bin/python scripts/import_retrieval_review_workbook.py /path/to/retrieval_review_v1.xlsx
./.venv/bin/python scripts/evaluate_retrieval_workbook_review_v1.py
```

The evaluation uses grade 2 as direct support, grade 1 as partial support,
grade 0 as not relevant, and `uncertain` as unjudged. Because the workbook
contains only a retrieval-generated candidate pool, the resulting scores are
candidate-pool diagnostics and not exhaustive relevance metrics. Do not use
these labels to promote production settings.

The API-aligned top-3 diagnostic calls the current `TacticalService` on every
development question. Run `scripts/evaluate_backend_workbook_review.py`; its
outputs are `reports/retrieval_backend_workbook_evaluation_v1.md` and the
per-question CSV. This measures serving-path behavior but inherits the same
provisional and incomplete qrels.

## Purpose

Review whether a UEFA report page provides evidence that answers each
development question. This is a page-relevance task, not a vote on the best
football tactic and not an evaluation of generated prose. StatsBomb events are
not part of these page judgments.

## Reviewer packet

`retrieval_human_review_packet_v1.csv` contains the 42 development questions
and candidate UEFA pages suggested by the union of the existing TF-IDF, fixed
BM25, graph retriever, dense MiniLM retrieval, and current labeled pages. Candidate order is shuffled
deterministically per question; retrieval ranks and channel names are omitted
to reduce ranking bias. The packet includes full page-bounded text and blank
review fields. It is a candidate pool, not an exhaustive set of all report
pages. Reviewers should record additional report/page references they find
through report contents or targeted full-report search.

Regenerate the packet from the fixed local indexes and chunks with:

```bash
./.venv/bin/python scripts/build_retrieval_human_review_packet.py
```

## Rating rubric

- **2 — Direct support:** the page contains relevant evidence that substantively
  answers the question. Record the supporting passage or section.
- **1 — Partial support:** the page is materially related and provides useful
  context, but cannot answer the question on its own. Record what it supports
  and what is missing.
- **0 — Not relevant:** the page does not materially support the question, even
  if it shares a keyword or competition.
- **uncertain:** the page is ambiguous, too fragmentary, or cannot be judged.
  Add a reason; do not force a positive or negative label.

The primary binary qrels should count grade 2 as relevant. Keep grade 1
separate for graded metrics or later analysis; do not silently turn topical
similarity into direct support. A question can have multiple grade-2 pages or
no grade-2 pages. If no report page supports it, record that explicitly after
searching the reports.

## Review process

1. Use at least two independent reviewers for each question-page pair. At
   least one should have football coaching or performance-analysis experience;
   record actual background in the sheet. Reviewers work independently and
   do not see one another's scores or system ranks.
2. Review the page in the context of its question. Score each page, quote the
   supporting text for grades 1 or 2, and explain uncertainty or limitations.
   A page that only repeats a term is not direct support.
3. Search for omitted relevant pages in the fixed five-report corpus. Add each
   discovered source ID and page to the packet before finalizing that
   question's qrels. The search is necessary because the ranked candidate pool
   can miss relevant pages.
4. Adjudicate disagreements between reviewers. Preserve the two original
   ratings and add a separate adjudication note; never overwrite one review to
   make agreement appear higher.
5. Calculate agreement before adjudication (for example, exact agreement and
   weighted Cohen's kappa for two raters). Report the statistic, denominator,
   missing/uncertain cases, and adjudication count. Do not claim reliability
   from agreement after adjudication.
6. Freeze a new qrel version, document reviewer backgrounds and dates, and
   verify no page overlaps v1 or v2 held-out qrels. Only then rerun development
   comparisons. Do not use the held-out labels for retriever selection.

## Interpretation and limitations

The five reports are static UEFA Technical Observer reports, not an
exhaustively annotated coaching-answer manual. Human page relevance means a
reviewer judged the page relevant to this question under this rubric; it does
not establish that the page is universally correct coaching advice. Do not
describe the existing AI-assisted labels as human-reviewed until completed
review sheets and adjudication records exist.
