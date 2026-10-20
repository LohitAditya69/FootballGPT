# Lap 8A — Improve UEFA evidence quality and passage retrieval

## Objective

Make the UEFA evidence supplied to answer generation readable, page-accurate, and responsive to the question. The screenshots show page chunks that merge paragraphs, report headings, player/match details, and unrelated material. The answer then inherits those artifacts and may combine overlapping chunks.

This lap owns UEFA text preparation and passage selection only. It does not change frontend rendering, historical-event scoring, answer-writing policy, or the shared API contract.

## Current symptoms to investigate

- The returned passage for `uefa-weuro-2025 p.68` combines multiple parts of the page, including running report text and match-specific detail.
- The returned `uefa-uwcl-2024-25 p.69` excerpt contains multiple topics and apparent extraction/layout artifacts.
- The serving path returns two chunks from page 68 (`c1` and `c2`) along with page 69. They may overlap or duplicate the same evidence.
- The displayed passages are returned as quotes. Retrieval-only cleanup must not silently turn altered or paraphrased text into a verbatim quotation.

## Read first

- `reports/product_api_contract_v1.md` — shared response schema and citation rules.
- `reports/evaluation_scope_lock.md`, `reports/uefa_gold_standard_protocol.md`, and `reports/retrieval_human_review_protocol.md` — benchmark boundaries and label limitations.
- `scripts/prepare_evidence.py`, `scripts/build_bm25_index.py`, `scripts/build_vector_index.py`.
- `backend/retrieval/vector_retriever.py`, `backend/retrieval/combined_retriever.py`, `backend/api/service.py`, and relevant tests.
- `reports/retrieval_development_evaluation.md` and `reports/retrieval_workbook_review_evaluation_v1.md` — development-only results and their caveats.

## Change boundary

May edit only the evidence-preparation/index-building and backend retrieval files needed for this lap, their focused backend tests, and this report for status/results. Expected candidates are:

- `scripts/prepare_evidence.py`, `scripts/build_bm25_index.py`, `scripts/build_vector_index.py`.
- `backend/retrieval/vector_retriever.py`, `backend/retrieval/combined_retriever.py`, and narrowly required `backend/api/service.py` changes.
- Focused tests under `backend/api/` or backend retrieval tests.
- This file for implementation notes and results.

Do not edit `frontend/**`, source PDFs, the report manifest, evaluation questions, qrels, workbook, the shared API contract, historical retrieval, answer-generation modules, or unrelated project files. Regenerated UEFA chunks and indexes are derived data containing report text: keep them local and excluded from commits/pushes, consistent with the user's instruction not to upload UEFA files. Do not commit, push, merge, rebase, or switch branches. Inspect Git status first and preserve all existing work. If the proposed fix requires changing the shared schema or another out-of-boundary path, stop and request approval with the exact reason.

## Requirements

1. Reproduce the reported examples from page 68 and 69 by tracing each returned `evidence_id` to its original PDF page and to `backend/data/uefa_evidence_chunks.jsonl`.
2. Fix extraction/chunking so page boundaries are preserved and passages are built from coherent paragraph or sentence groups instead of arbitrary cross-paragraph word windows where practical. Keep a bounded maximum chunk length and deterministic output.
3. Preserve stable `source_id`, page, citation, and evidence provenance. If chunk IDs change, update only derived local indexes and tests that depend on them; never remap a citation to another page.
4. Keep source text and retrieval normalization distinct. Whitespace or verified header cleanup may be used for retrieval, but do not present transformed text as an exact quotation unless it has been checked against the PDF. Preserve a trace from every returned excerpt to its exact source/page.
5. Filter verified running headers, footers, and extraction artifacts from retrieval candidates only when the rule is conservative and documented. Do not remove valid names, tactical terms, or evidence because of broad uppercase/number heuristics.
6. Deduplicate near-identical or overlapping candidates before response selection. Prefer a small set of distinct, directly relevant source passages; do not fill the result limit with duplicate chunks from the same page.
7. Retrieval rank is candidate ordering, not proof of support. Keep or strengthen the existing answerability/relevance gate; if the available passage does not answer the question, retain safe abstention rather than promoting a weak candidate.
8. Keep development tuning on development material only. The v1 and v2 held-out sets remain frozen and must not be used for choosing chunking, filters, thresholds, weights, or prompts.

## Validation and evaluation

- Compare the extracted text for UEFA report pages 68 and 69 against the actual PDF page layout; record concrete artifacts found and the resulting clean chunks.
- Add regression cases for the winning-the-ball question and for irrelevant/ambiguous questions. Check both retrieved passage IDs and exact excerpt/source-page linkage.
- Evaluate the existing workbook prototype and AI-assisted development labels only as provisional diagnostics. Report P@5, Recall@5, MRR (where available), duplicate rate, and the number of questions that abstain; state the limits of those labels.
- Do not call the workbook's scripted profiles human/coach review or ground truth. Do not claim an improvement from retrieval scores alone if evidence cleanliness or direct support worsens.
- Run the focused backend test suite and the existing development evaluation. Record the exact commands, results, and any platform-dependent failures here.

## Acceptance checklist

- [ ] Page 68 and 69 extraction defects have been traced to their preparation/index stage and corrected conservatively.
- [ ] Returned passages remain page-cited and traceable; no altered text is presented as an exact quote without verification.
- [ ] Overlapping/duplicate chunks do not crowd out distinct direct evidence.
- [ ] Weak or non-responsive evidence still leads to abstention.
- [ ] Development evaluation and relevant regressions are recorded without using v1/v2 held-out material for tuning.
- [ ] UEFA source PDFs remain unchanged; generated report-text indexes remain local and excluded from publication.
- [ ] No frontend, contract, historical-event, or answer-generation behavior was changed by this lap.
- [ ] No commit or push was created.

## Handoff to Lap 9A

Provide the verified page/chunk identifiers for the winning-the-ball example, note any remaining source-text limitations, and identify whether a reliable event sequence can be derived from the existing StatsBomb candidate corpus. Lap 9 must not use a UEFA passage as a substitute for historical event evidence.

## Status

- [x] Page 68 and 69 extraction defects were traced to extraction/layout handling and corrected conservatively. The five manifest PDFs were present under `UEFA Reports/`; their SHA256 hashes and page counts matched the manifest. WEURO p.68 and UWCL pp.68–69 were rendered and visually checked. PDFium's embedded extraction was rejected after adjacent pages were found duplicated/mis-mapped; extraction uses Poppler `pdftotext -layout -enc UTF-8`, with no OCR-derived text.
- [x] `scripts/prepare_evidence.py` now produces page-local, column-aware sentence-group chunks with an 180-word maximum. Original `text` is retained separately from normalized `retrieval_text`. No page crossing or overlap is introduced.
- [x] API excerpts are selected for query relevance but remain literal substrings of the source chunk. Candidate response selection keeps one result per source/page and suppresses near-identical excerpts. The winning-ball smoke query includes `uefa-uwcl-2024-25:p69:c4`; its excerpt begins “After winning the ball in their own half, the first pass was usually played directly deep or diagonally…”, and source/page metadata matches the chunk record.
- [x] Rebuilt local derived data: 3,079 UEFA chunks, BM25 and TF-IDF indexes, and the provenance graph (27,567 nodes; 54,886 edges). Rebuilding the graph was needed because its evidence nodes use chunk IDs. These text-bearing outputs remain local and are excluded from the commit.
- [x] `python -m unittest backend.api.test_uefa_retrieval_quality -v` — 8 focused tests passed, including bounded page-local chunks, column separation, verbatim excerpts, distinct pages, source linkage, and irrelevant/ambiguous abstentions. `git diff --check` passed. Broader pytest tests could not run because pytest is not installed.
- [x] A development-only run of the current API used the 22 original plus 20 v2 development questions (42 total); no held-out questions were used. With top-k set to 5: P@5 **0.271**, Recall@5 **0.393**, MRR **0.528**, nDCG@5 **0.695**, Judged@5 **0.876**; 42 answered, 0 abstained, 0 duplicate source/page pairs among returned results. Seven questions had no grade-2 workbook page. These are provisional scripted workbook labels over retrieval-generated candidates, not human/coach judgments or ground truth. Zero abstentions on this dev set is not proof of general answerability. The previous AI-assisted development-qrel scores were not recomputed and remain a baseline only.
- [x] No frontend, contract, historical-event, or answer-generation code was changed. Source PDFs were not changed. No ranking weights or thresholds were tuned. The pinned dense-vs-BM25 comparison remains unavailable because its model revision is not cached.

The user subsequently explicitly requested pushing this work to `main`; that request supersedes the original no-push handoff instruction. Local `main` was fast-forwarded to `origin/main` before preparing this commit, preserving its two newer commits. Only source code, the focused test, and this report are intended for the commit. No UEFA-derived text/index files are included.
