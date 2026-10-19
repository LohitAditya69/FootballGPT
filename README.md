# FootballGPT

## Main project idea

FootballGPT is an NLP decision-support system for football tactics. Given a
natural-language tactical question, it retrieves evidence from coaching
materials and historical match events, then produces a report whose claims can
be checked against that evidence.

Graph-Guided Tactical Retrieval (GGTR) combines three signals:

```text
score = α × V + β × G + γ × H
```

- **V — Vector similarity:** semantic match between a question and tactical text.
- **G — Graph relevance:** links among football concepts, teams, formations, and events.
- **H — Historical similarity:** past match situations with similar event characteristics.

The Reasoning Graph Generator (RGG) exposes the evidence path as JSON linking
the question to retrieved text and match examples. The project stays focused on
text retrieval, structured match-event data, grounded generation, and
explainability.

## Step-by-step checklist

1. [x] Locate the project and verify the local raw and processed datasets.
2. [x] Inspect the existing train/test counts and sample case schema.
3. [x] Scan the saved train/test files: match-level overlap is zero and row counts match the summary.
4. [x] Create 12 test-split question/evidence seeds with raw trigger references.
5. [x] Freeze the five 2024/25 and 2025 UEFA Technical Observer reports with SHA-256 manifest.
6. [x] Lock the 12 revised test questions, page-level UEFA references, event evidence, and evaluation metrics; label uncovered items explicitly.
7. [x] Create an auxiliary, source-linked FIFA tactical-principle seed corpus; exclude it from the locked UEFA reference set.
8. [x] Prepare page-cited UEFA report chunks and bounded StatsBomb evidence windows for the locked test questions.
9. [x] Build a bounded NetworkX graph from match and tactical entities (**G**).
10. [x] Implement historical-match filtering and similarity (**H**).
11. [x] Combine normalized scores with GGTR; retain `αV + γH` if graph construction is impractical.
12. [x] Compare vector-only, `V + G`, and full GGTR using Precision@k, Recall@k, and MRR for the page-labeled scope.
13. [x] Generate extractive, citation-grounded evidence briefs and a human factuality review sheet; independent factuality scoring remains pending.
14. [x] Produce RGG provenance JSON and render the evidence path in a browser view.
15. [x] Document ablation results, limitations, project status, and commit-history contributions.

## Locked evaluation scope

The frozen corpus, 12 prompts, page/event annotations, metrics, baselines, abstention rules, and historical-match leakage rule are documented in `reports/evaluation_scope_lock.md`. Hashes for the five reports are in `reports/uefa_report_manifest.json`. Retrieval metrics have been run as pilots. Lap 1 integrity checks passed for citations, raw event windows, provenance, and abstentions, but only 3 of 30 displayed citations matched locked target pages (across 2 of 10 covered questions); see `reports/reliability_review_lap1.md`. This is an alignment diagnostic, not an independent factuality score. The answer pipeline produces verbatim, cited evidence briefs, not free-form recommendations; independent factuality scoring remains pending human review.

## Grounded answer and provenance pipeline

With the project environment installed, regenerate the 12 frozen test-question briefs, Reasoning Graph Generator (RGG) provenance traces, factuality review sheet, and browser view with:

```bash
./.venv/bin/python scripts/generate_grounded_reports.py
```

Open `reports/generated/index.html` to browse each question, its verbatim UEFA passages, recorded StatsBomb event window, and retrieval provenance. Machine-readable outputs are `reports/generated/grounded_reports.jsonl` and `reports/generated/rgg_provenance.jsonl`. The blank `reports/generated/factuality_review.csv` is a reviewer worksheet, not a scored evaluation. Two questions marked `not_covered` by the locked reference annotations abstain and show no tactical passages. The report generator does not use the gold reference answers to compose responses and does not infer off-ball runs, team shape, or unseen video context.

See `reports/project_status_and_contributions.md` for the completed pipeline stages, remaining human-review work, pilot limitations, and contribution summary based on Git history.

The next work is staged in `reports/reliability_and_product_workflow.md`: Lap 1 audits benchmark and generated-evidence reliability, Lap 2 builds the backend and freezes its API contract, and Lap 3 builds the frontend against that contract. Each product lap has two parts and integration checkpoints.

## Tactical text seed corpus

`backend/data/tactical_sources.jsonl` contains four short, paraphrased coaching-principle records from FIFA Training Centre pages on high pressing, switching play, counter-attacking, and reacting to loss of possession. Each record keeps its source URL and is explicitly marked as auxiliary. These are AI-curated summaries for retrieval prototyping, not UEFA materials, full-text manuals, or gold-standard answers. They are excluded from the gold evaluation corpus. Check source reuse terms before storing or distributing full article text.

The five static UEFA Technical Observer reports must be present locally in `UEFA Reports/`; their exact hashes and page counts are in `reports/uefa_report_manifest.json`. The PDFs are intentionally excluded from Git to keep the push within file-size limits. To regenerate report evidence, supply the exact hash-matching PDFs at the manifest paths. The source pages and StatsBomb event references for the 12 questions are locked in `reports/evaluation_seed_questions.csv` and `reports/evaluation_scope_lock.md`. Two questions are explicitly not covered by the UEFA reports. No live coach review is part of this evaluation. Match facts use StatsBomb; tactical principles use cited UEFA pages.

## Prepared evidence

Step 8 is complete. `backend/data/uefa_evidence_chunks.jsonl` contains 765 reproducible text chunks from the five hash-locked UEFA PDFs; each record preserves the report ID, PDF hash, page citation, chunk position, and text. Chunks are page-bounded (300 words with 40-word overlap), so retrieval can cite the source page directly. `backend/data/question_event_evidence.jsonl` contains one window per locked test question, with the trigger event and up to five adjacent file-order events on either side. Event records preserve selected raw StatsBomb fields, including shot freeze-frame data when present. These windows expose recorded event evidence only; they do not establish unseen team shape, runs, or other video context.

Regenerate both evidence files from the locked source manifest and question CSV with:

```bash
python3 scripts/prepare_evidence.py
```

The script checks source hashes, report page counts, and unique trigger IDs before writing. It requires `pdftotext` (Poppler) for PDF text extraction.

## Retrieval graph (**G**)

Step 9 is complete. `backend/data/retrieval_graph.json` is a portable NetworkX `MultiDiGraph` export with report, page, chunk, tactical-concept, event-window, match, event, team, formation, and player nodes. UEFA evidence links to concepts through a fixed alias vocabulary; event links come from recorded StatsBomb event types and entities. It includes 10,023 deterministic train-only situations (up to three per match) plus the 12 prepared pilot event windows. No question wording, gold answers, qrels, or evaluation annotations are graph nodes or edges. Formation fields are sparse (107 sample rows) and remain attributed to the case data rather than inferred from events. Concept alias links are a transparent lexical index and can miss paraphrases or match a term in an irrelevant context.

Install the graph dependency and rebuild after evidence preparation:

```bash
python3 -m pip install -r requirements-graph.txt
python3 scripts/sample_train_situations.py
python3 scripts/build_retrieval_graph.py
```

The manifest at `backend/data/retrieval_graph_manifest.json` records input and graph hashes and node/edge counts. `backend/retrieval/graph_retriever.py` exposes `load_graph()` and `retrieve_graph()` as the initial graph-only **G** retrieval signal; it returns page citations and graph scores for UEFA chunks. Graph scores are lexical/structural only and are not evaluation results.

## Retrieval pipeline checklist

1. [x] **V — Retrieval comparison:** sparse TF-IDF/BM25 and a dense MiniLM development retriever have been compared; dense was not promoted because it underperformed and the labels remain provisional.
2. [x] **G — Graph retrieval:** link training-split teams, available formations, events, and tactical concepts without adding gold labels.
3. [x] **H — Historical retrieval:** index train-split match situations and exclude the query match from candidates.
4. [x] Normalize V, G, and H scores to a shared 0–1 range.
5. [x] The offline combined retriever supports `S = αV + βG + γH`; the live API combines V/G for UEFA passages and returns H as a separate, explicitly labeled example channel.
6. [x] Keep `S = αV + γH` as the documented fallback only if G proves infeasible; it is inactive because G was built.

### Primary prototype evaluation

The workbook-based scorecard in `reports/retrieval_workbook_review_evaluation_v1.md`
is now the primary day-to-day prototype evaluation. Refresh the rankings with
`scripts/compare_dense_retrieval_on_dev.py`, import the unchanged workbook with
`scripts/import_retrieval_review_workbook.py`, then score it with
`scripts/evaluate_retrieval_workbook_review_v1.py`. These labels come from
scripted reviewer profiles and a retrieval-generated candidate pool, so this
is a prototype diagnostic only—not human/coach validation or publication
evidence. Keep the production config unchanged unless later independent review
supports a consistent gain.

To evaluate the actual API ranker, run
`scripts/evaluate_backend_workbook_review.py`; its current top-3 results are in
`reports/retrieval_backend_workbook_evaluation_v1.md`. A spot audit of two
direct-support labels is in `reports/retrieval_workbook_label_audit_v1.md`.
That audit found both page-level labels defensible, while one selected quote
needs a better supporting sentence and the other target page is still missed
by the API top three. The API-aligned V:G sensitivity sweep slightly favors
BM25-only on P@3, recall, and nDCG while tying MRR; it is not promoted because
the workbook labels are provisional and were reused for selection.

An exploratory 128-setting BM25/graph sweep is available in
`scripts/tune_retrieval_on_workbook.py`; results are in
`reports/retrieval_workbook_tuning_v1.md`. Its top candidate improved nDCG@5
and MRR slightly but reduced recall, so it was not promoted and the serving
configuration remains unchanged. The same script runs a candidate-depth
diagnostic (`reports/retrieval_workbook_candidate_pool_v1.csv`): a wider pool
slightly raises direct P@5/recall, while nDCG stays flat and judged coverage
falls. This is not enough evidence to change the serving depth.

The v1 and v2 sets are no longer the primary prototype scorecard. Keep their
questions, qrels, and reports as frozen archived holdouts for regression and
final evaluation; never tune on them or delete them. The development semantic
comparison and historical H proxy remain supporting diagnostics.

Retrieval development and held-out results are in `reports/retrieval_development_evaluation.md`, `reports/retrieval_evaluation.md` (v1), and `reports/retrieval_v2_heldout_evaluation.md` (20 new held-out questions); per-question tables accompany the reports. Benchmark v2 adds 20 development and 20 held-out questions across all five UEFA reports, with page-disjoint splits. Tuning on 42 development questions selected BM25 `k1=0.8`, `b=0.5`, and a 0.9:0.1 lexical-to-graph ratio. On the new 20-question held-out set, this scored P@5 0.080, Recall@5 0.400, MRR 0.292, versus fixed BM25 at 0.090, 0.450, 0.275; TF-IDF scored 0.090, 0.450, 0.283. The selected method only had slightly higher MRR, while the lexical baselines retrieved more target pages in the top five. The earlier v1 test is retained as a separate version; its selected settings are archived in `backend/retrieval/ranking_config_v1.json`. H has no judged relevance, and not-covered v1 questions have no calibrated abstention rule. All are pilot diagnostics.

The development labels support multiple source-qualified pages per question,
but page review remains incomplete. They are explicitly marked AI-assisted
and incomplete; they are not coach judgments or exhaustive qrels. The
development tuner evaluates labeled pages and guards against v1/v2 held-out
page overlap. With the current provisional labels, the 42-question run
selected BM25 `k1=1.5`, `b=0.25`, and graph weight `0.2` (P@5 0.181, Recall@5
0.655, MRR 0.634). This does not establish a consistent improvement, and the
production retrieval configuration remains the baseline. A blinded human
review packet with 1,071 question-page candidates is in
`reports/retrieval_human_review_packet_v1.csv`; the rating rubric and review
workflow are in `reports/retrieval_human_review_protocol.md`. Step 7's
development-only comparison is now implemented in
`scripts/compare_dense_retrieval_on_dev.py` and reported in
`reports/dense_retrieval_development_comparison.md`. On the current incomplete
AI-assisted qrels, dense MiniLM alone trails fixed BM25 (P@5 0.081 vs 0.171;
Recall@5 0.321 vs 0.619; MRR 0.259 vs 0.612). The 25%-dense hybrid is close to
BM25, while the current BM25+graph configuration remains slightly higher on
these provisional labels. No production configuration was changed. The
embedding runtime is pinned in the optional `requirements-embedding.txt`; the
cached MiniLM revision is recorded in the comparison report. Complete human
review before making a retrieval-quality claim or promoting a setting. Do not
tune on v1/v2 held-out sets.

The user-provided `retrieval_review_v1.xlsx` has now been used as a separate
prototype label input. It is unchanged and remains outside the repository. Its
two reviewer profiles are scripted, so the results are not human or coach
review and do not establish reviewer reliability. A compact export with IDs,
grades, and provenance (no page text or excerpts) is in
`reports/retrieval_workbook_review_qrels_v1.csv`; the separate rescoring and
per-question results are in `reports/retrieval_workbook_review_evaluation_v1.md`
and `.csv`. The workbook-based evaluation reports direct support, partial
support, graded nDCG, and how much of each retrieved top five was judged. Treat
it as a prototype diagnostic; production settings remain unchanged. The import
and rescore commands are documented in
`reports/retrieval_human_review_protocol.md`.

The latest retrieval/backend test run is summarized in
`reports/retrieval_test_run_v1.md`. The v1/v2 retrieval evaluations,
development comparisons, and match-disjoint H proxy all completed. The H
near-ceiling metrics are self-confirming because the proxy labels reuse the
retriever's metadata fields. The API suite now passes all 13 tests; see the
report for the local interpreter setup and remaining label-quality limits.

Benchmark v2 questions and page annotations are in `reports/retrieval_benchmark_v2_questions.csv`. Validate the page/split lock with `python3 scripts/validate_retrieval_benchmark_v2.py`, tune only on development pages with `python3 scripts/tune_retrieval_on_dev.py`, build the selected BM25 index with `python3 scripts/build_bm25_index.py`, and run the new held-out evaluation once with `python3 scripts/evaluate_retrieval_v2_test.py`. Do not use the held-out results to retune.

Production V uses `backend/retrieval/vector_retriever.py` with sparse TF-IDF/BM25. A dense MiniLM comparator is implemented separately in `scripts/compare_dense_retrieval_on_dev.py`; it is an experiment and is not wired into the production API. Dense retrieval did not outperform BM25 on current AI-assisted development qrels, so the existing sparse baseline remains active. Indexes are `backend/data/uefa_tfidf_index.json` and `backend/data/uefa_bm25_index.json`.

Each component is min-max normalized per query over that retriever’s top `max(4 × requested_k, 20)` candidates. If a channel’s returned scores are all equal, each returned candidate receives 1.0; candidates absent from a channel receive 0.0. This puts the three returned score lists on a common 0–1 range without tuning calibration values against the locked questions. The rule is stored in `backend/retrieval/ranking_config.json` and implemented by `normalize_channel()`.

The generic offline fusion rule is `S = αV + βG + γH`. `backend/retrieval/ranking_config.json` records the v2 development-selected BM25 settings (`k1=0.8`, `b=0.5`) and V:G ratio (0.9:0.1); γ remains at its initial 1/3 because H has no independent relevance labels. `backend/retrieval/combined_retriever.py` accepts BM25 or TF-IDF and can fuse all three channels. In the live API, UEFA passages use the configured relative V:G weights; H runs only with grounded event context and is returned separately because historical event records are not UEFA coaching evidence. The API verifies its BM25 index parameters against this config at startup. The held-out set shows only a small MRR gain and lower top-five recall for the selected setting; it is not a clear overall improvement.

## Historical retrieval (**H**)

Step 3 is implemented in `backend/retrieval/historical_retriever.py`. `scripts/sample_train_situations.py` streamed the full 1,759,328-row train split and retained up to three deterministic hash-selected cases per match: 10,023 cases across 3,341 training matches. The compact, compressed candidate index is `backend/data/historical_train_sample.jsonl.gz`. It compares event type, play pattern, location, outcome, pressure, and counterpress metadata when available. Similarity weights are fixed at event type .40, play pattern .15, location .25, outcome .10, pressure .05, and counterpress .05, renormalized over fields present in both records. Team identity is excluded. Every H call requires `exclude_match_id`; candidates from that match are removed. This is a bounded pilot index, not all train rows.

For the next H-retrieval development step, `scripts/create_historical_dev_split.py`
creates a deterministic match-disjoint partition within the original training
matches: 334 matches for development queries and 3,007 for candidate retrieval.
The source train/test files remain untouched; the original test split was not
read. The split manifest is `reports/historical_retrieval_match_split_v1.json`
and its rules are documented in `reports/historical_retrieval_development_split.md`.
The current all-training-match sample must be filtered by the candidate IDs
before it is used as the development index. `scripts/sample_historical_dev_candidates.py`
now produces nested candidate samples of 3, 10, and 25 cases per candidate
match under `/private/tmp/footballgpt_historical_candidates_v1/`; they cover
all 3,007 candidate matches and total 9,021, 30,070, and 75,175 records. The
sample-size comparison measures coverage and storage. A development-only
comparison of the unchanged H ranker against a fixed metadata-similarity proxy
is also documented there: MRR@5 reached 1.000 at each size, while Recall@5
rose from 0.010 to 0.014. These near-ceiling results are self-confirming
because the proxy labels and ranker share event-type, play-pattern, and
location features. They do not show tactical retrieval quality and must not
be used to choose production index size or tune H weights. The 25-per-match
sample remains a reference pool for this diagnostic, not the complete set of
training cases.

## Data already present

The local StatsBomb Open Data snapshot is in `archive (3)/` with the standard
`data/events`, `data/matches`, `data/lineups`, and `data/three-sixty` layout:

- 4,235 event files: 4,201 valid JSON arrays and 34 rate-limit error text placeholders
- 4,235 lineup files: 4,233 valid JSON files and 2 rate-limit error text placeholders
- 80 competition/season match files and entries in `competitions.json`
- 426 360-data JSON files

The 36 invalid files contain “Sorry, the service is temporarily unavailable due
to too many requests. Please try again later.” They are not JSON. The processed
case corpus covers all 4,201 matches with valid event files; do not rerun
processing on the 34 invalid event files until they are repaired.

The project also contains:

- 300 SoccerNet `Labels-v2.json` files under `backend/data/soccernet_raw`
- One older StatsBomb CSV sample under `backend/data/statsbomb_raw`
- A prebuilt `cases_output_full/` corpus with 2,213,667 cases: 1,759,328 train
  and 454,339 test records. Its JSONL files total about 79 GiB.

The train/test scan found zero overlapping match IDs, no missing IDs in case
records, and exact agreement with `summary.json`. The audit and question seeds
are in `reports/case_corpus_audit.md` and
`reports/evaluation_seed_questions.csv`.

All 12 seed trigger IDs, event types, and timestamps were checked against the
raw match files. The case builder's phase and field-zone labels remain
heuristics, not reference facts. The CSV now contains fixed UEFA page-grounded
reference annotations, StatsBomb event references, and explicit conditional or
not-covered labels; no live coach review is claimed. Stream JSONL files instead
of loading the full corpus into memory.

## Inspect the local StatsBomb files

The inventory helper reads the existing dataset and does not download anything:

```bash
python backend/data_ingestion/load_statsbomb.py
python backend/data_ingestion/load_statsbomb.py --list-seasons
```

The existing case corpus is ready for downstream retrieval work. To regenerate
a small sample from the raw StatsBomb snapshot, the case builder accepts the
repository root directly:

```bash
python tactical_case_builder.py 'archive (3)' --max-matches 3 --skip-excel \
  --output-dir /private/tmp/footballgpt_case_preview
```

Do not run a full regeneration unless the case-generation rules need to change.
Credit StatsBomb when publishing or sharing analysis based on its data.
