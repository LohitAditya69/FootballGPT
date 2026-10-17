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
12. [ ] Compare vector-only, `V + G`, and full GGTR using Precision@k, Recall@k, and MRR.
13. [ ] Generate citation-grounded reports and measure factual errors against the fixed UEFA references.
14. [ ] Produce RGG provenance JSON and render it in the interface.
15. [ ] Document ablation results, limitations, and team contributions.

## Locked evaluation scope

The frozen corpus, 12 prompts, page/event annotations, metrics, baselines, abstention rules, and historical-match leakage rule are documented in `reports/evaluation_scope_lock.md`. Hashes for the five reports are in `reports/uefa_report_manifest.json`. The locked question set is a 12-question pilot; model scores have not been run.

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

1. [ ] **V — Semantic vector retrieval:** the sparse TF-IDF vector baseline is built; dense embedding-based semantic retrieval remains pending.
2. [x] **G — Graph retrieval:** link training-split teams, available formations, events, and tactical concepts without adding gold labels.
3. [x] **H — Historical retrieval:** index train-split match situations and exclude the query match from candidates.
4. [x] Normalize V, G, and H scores to a shared 0–1 range.
5. [x] Combine them with `S = αV + βG + γH` and document the selected weights.
6. [x] Keep `S = αV + γH` as the documented fallback only if G proves infeasible; it is inactive because G was built.

V uses `backend/retrieval/vector_retriever.py`; rebuild its index with `python3 scripts/build_vector_index.py`. The current implementation is a deterministic sparse lexical vector baseline (unigrams and adjacent bigrams), not a dense neural embedding model. A dense model could not be installed because the package index was unreachable, so semantic paraphrase matching remains a limitation. The vector index is `backend/data/uefa_tfidf_index.json`.

Each component is min-max normalized per query over that retriever’s top `max(4 × requested_k, 20)` candidates. If a channel’s returned scores are all equal, each returned candidate receives 1.0; candidates absent from a channel receive 0.0. This puts the three returned score lists on a common 0–1 range without tuning calibration values against the locked questions. The rule is stored in `backend/retrieval/ranking_config.json` and implemented by `normalize_channel()`.

The fusion rule is `S = αV + βG + γH`. The fixed starting configuration uses equal weights (`α = β = γ = 1/3`) in `backend/retrieval/ranking_config.json`; `backend/retrieval/combined_retriever.py` loads the config and returns component scores alongside the fused score. The weights are an initial baseline, not values selected by tuning on the 12 locked questions. Mixed-source results include UEFA chunks from V/G and train-only match situations from H.

## Historical retrieval (**H**)

Step 3 is implemented in `backend/retrieval/historical_retriever.py`. `scripts/sample_train_situations.py` streamed the full 1,759,328-row train split and retained up to three deterministic hash-selected cases per match: 10,023 cases across 3,341 training matches. The compact, compressed candidate index is `backend/data/historical_train_sample.jsonl.gz`. It compares event type, play pattern, location, outcome, pressure, and counterpress metadata when available. Similarity weights are fixed at event type .40, play pattern .15, location .25, outcome .10, pressure .05, and counterpress .05, renormalized over fields present in both records. Team identity is excluded. Every H call requires `exclude_match_id`; candidates from that match are removed. This is a bounded pilot index, not all train rows.

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
