# Evaluation scope lock v1

**Locked:** 2026-10-17  
**Project:** FootballGPT tactical question answering  
**Evaluation set:** 12 revised questions sampled from the saved StatsBomb test split. Original wording remains in `evaluation_seed_questions.csv`; `revised_question_seed` is the frozen prompt text.

## Fixed reference corpus

Use only these five local UEFA reports as the fixed tactical-reference corpus. The files and SHA-256 hashes are recorded in `uefa_report_manifest.json`; changing a PDF requires a new corpus version and lock. UEFA describes these as reports produced by its Technical Observer Group with performance-analysis support. They contain static observer analysis and coaching insights. They are technical reports, not pre-labeled question-answer manuals; the page-level annotations in the CSV are the benchmark’s static evidence labels.

| Source ID | Competition and edition | File | Pages |
|---|---|---|---:|
| `uefa-ucl-2024-25` | UEFA Champions League 2024/25 Technical Report | [`UCL_Technical-Report_2025_DIGITAL.pdf`](../UEFA Reports/UCL_Technical-Report_2025_DIGITAL.pdf) | 120 |
| `uefa-uwcl-2024-25` | UEFA Women’s Champions League 2024/25 Technical Report | [`pdf-uwcl-2025-technical-report.pdf`](../UEFA Reports/pdf-uwcl-2025-technical-report.pdf) | 92 |
| `uefa-uel-2024-25` | UEFA Europa League 2024/25 Technical Report | [`pdf-uel-2025-technical-report_v2.pdf`](../UEFA Reports/pdf-uel-2025-technical-report_v2.pdf) | 96 |
| `uefa-uecl-2024-25` | UEFA Conference League 2024/25 Technical Report | [`pdf-uecl-2025-technical-report.pdf`](../UEFA Reports/pdf-uecl-2025-technical-report.pdf) | 92 |
| `uefa-weuro-2025` | UEFA Women’s EURO 2025 Technical Report | [`WEURO2025_Technical-Report_2025_DIGITAL.pdf`](../UEFA Reports/WEURO2025_Technical-Report_2025_DIGITAL.pdf) | 96 |

StatsBomb raw events remain the reference for what happened in each sampled match. UEFA reports ground tactical principles and observed examples. Neither source is used to invent missing context.

## Frozen question-to-evidence annotations

The twelve questions remain in the test split and are grouped into four families: three attacking-transition questions (1-3), three build-up/event-context questions (4-6), three pressing questions (7-9), and three finishing/transition questions (10-12). The CSV contains each fixed answer annotation, UEFA source/pages where applicable, and StatsBomb event references.

- **Conditional UEFA support (10 questions):** the report supports a tactical principle, but not a unique best decision for the historical frame. Answers must remain conditional on visual details not present in the event window.
- **Not covered by UEFA (2 questions):** questions 5 and 6 concern continuity/restart interpretation of particular event sequences. Use the StatsBomb chronology and mark missing video context; do not cite an unrelated manual passage as support.
- No live coach review is part of this benchmark. The standard is the frozen report text plus the linked StatsBomb events. An annotation does not claim universal coaching truth.

## Evaluation protocol

1. Freeze the five report files, the 12 prompt strings, and the page/event annotations before running retrieval or generation. Do not tune on these 12 questions.
2. For report retrieval, use page-level relevance labels in `gold_qrel_pages`; compute Precision@5, Recall@5 and MRR over the ten questions with relevant UEFA pages. Evaluate the two not-covered questions separately for correct abstention/no-match rather than assigning irrelevant pages as positives.
3. Compare vector-only (**V**), vector plus graph (**V+G**), and full GGTR (**V+G+H**) with the same corpus and query set. Keep embeddings, chunking, graph, and scoring settings fixed across the comparison.
4. For generated answers, score (a) tactical claims supported by cited UEFA page(s), (b) match facts supported by cited StatsBomb event IDs, (c) unsupported-claim rate, and (d) appropriate conditional answers/abstentions. A correct answer must not turn an AI-generated case-builder phase/zone/action heuristic into a source fact.
5. For historical similarity (**H**), retrieve from the train split only and exclude the query match ID from every candidate pool.
6. Report per-question results and macro averages. With only 12 questions, describe findings as a pilot; do not claim broad statistical generalisation.

## Locked question/source map

| Q | Case ID | Reference pages | Manual support |
|---:|---|---|---|
| 1 | `69289:case:214` | UCL pp.90-91 | conditional |
| 2 | `3912477:case:3097` | UWCL pp.69-71; Women’s EURO pp.68-70 | conditional |
| 3 | `3901194:case:2486` | UCL pp.90-91 | conditional |
| 4 | `267212:case:1599` | UCL pp.68-75, especially pp.74-75 | conditional |
| 5 | `3749448:case:2695` | No relevant UEFA page; event-context item | not_covered |
| 6 | `3912184:case:643` | No relevant UEFA page; event-context item | not_covered |
| 7 | `3890333:case:1948` | UCL pp.30-31 and pp.80-85 | conditional |
| 8 | `3754143:case:192` | UCL pp.30-31 and pp.80-85 | conditional |
| 9 | `3930174:case:2413` | UCL pp.30-32 and pp.80-85 | conditional |
| 10 | `3879802:case:373` | UCL p.26 | conditional |
| 11 | `15956:case:1769` | UCL p.26; p.67 for goal-location context | conditional |
| 12 | `3754043:case:3303` | UCL pp.26 and 90-91 | conditional |

## Exit criteria for the scope/evaluation step

- The exact five PDFs are present and hash-locked.
- The 12 test prompts have fixed wording, source page mappings or explicit not-covered labels, gold-reference answers, and event references.
- Metrics, baselines, abstention handling, and match-leakage rule are fixed before benchmark execution.

This locks the scope and scoring protocol. A V/G/H retrieval prototype and fixed score-fusion configuration are implemented below. The locked retrieval benchmark has now been run; answer-generation and factuality scores remain pending.

## Retrieval improvement addendum (2026-10-17)

After the initial comparison, a second conventional sparse lexical method was added: BM25 with fixed `k1=1.5`, `b=0.75`, and the already locked tokenizer/chunks. These values were set by the standard method, not fitted to the 12 prompts. It was benchmarked once against the same frozen qrels as an exploratory baseline; no settings were changed in response. This does not create a development set and must not be treated as permission to optimize on the locked questions. Any further tuning requires a separate development set. See `retrieval_evaluation.md` for the mixed outcome.

## Separate development tuning record

A separate set of 22 AI-drafted tactical questions was added in `retrieval_development_questions.csv`, targeting report pages that do not occur in the locked qrels. The tuning script checks this page-level non-overlap before running. BM25 `k1`/`b` and the relative V:G weight were selected on development data using MRR, then Recall@5, then P@5. The selected `k1=2.0`, `b=0.5`, V:G ratio 0.7:0.3 raised development MRR from 0.600 to 0.644. On the locked questions it scored below fixed BM25 on all three metrics (P@5 0.120 vs 0.140; Recall@5 0.111 vs 0.122; MRR 0.267 vs 0.300). This is evidence that this development set did not predict held-out performance. The locked set was not used to retune or select a replacement. Review the development labels and expand the set before another tuning round.

## Expanded benchmark v2

`retrieval_benchmark_v2_questions.csv` adds 20 development questions and 20 new held-out questions across all five reports. The validation script confirms that every page exists, all 20 held-out target pages are unique, and they do not overlap the v1 qrels, either development set, or each other. Tuning used 42 development questions total and selected BM25 `k1=0.8`, `b=0.5`, V:G ratio 0.9:0.1. On the new 20-question held-out set, selected BM25+G scored P@5 0.080, Recall@5 0.400, MRR 0.292; fixed BM25 scored 0.090, 0.450, 0.275; TF-IDF scored 0.090, 0.450, 0.283. This is a small MRR improvement but lower top-five retrieval rates, so there is no clear overall improvement. The questions and page labels are AI-drafted from report text, not independent coach judgments. Keep v1 and v2 results separate and do not tune on v2 held-out questions.

## Graph implementation record

The bounded graph implementation is `retrieval-graph-v2`, exported as `backend/data/retrieval_graph.json` and described by `backend/data/retrieval_graph_manifest.json`. It contains page-bounded UEFA text, the 12 pre-extracted StatsBomb event windows, and 10,023 deterministic train-only situations sampled at up to three per match. It links recorded teams, events, available formation values, and concepts; only 107 sampled rows have a formation value. The graph builder excludes question text, gold answers, qrels, and annotation labels. UEFA concepts are attached using a fixed curated alias vocabulary; event concepts use broad StatsBomb event-type mappings. The initial **G** signal retrieves UEFA chunks directly linked to query-matched concepts, with a 0.25 one-hop expansion through a concept group; scores are normalized to [0, 1]. No parameters were tuned against the 12 questions and no benchmark scores are claimed. Preserve this graph version, vocabulary, and scoring rule for the first V versus V+G comparison; if they change, record a new graph version before measuring.

The initial **H** candidate pool is `backend/data/historical_train_sample.jsonl.gz`, derived only from the 1,759,328-row train split by deterministic hash selection (at most three cases per match). Similarity compares event type (.40), play pattern (.15), pitch location (.25), event outcome (.10), pressure (.05), and counterpress (.05), renormalizing across jointly available fields. Team identity is not a similarity feature. Every H query must provide `exclude_match_id`, and candidates from that match are excluded. The sample contains 10,023 cases from 3,341 matches. These weights and the sample cap are fixed initial settings, not tuned benchmark results.

Initial fusion configuration is recorded in `backend/retrieval/ranking_config.json`: each channel is per-query min-max normalized over its top `max(4k, 20)` candidates (constant returned scores map to 1.0; absent candidates map to 0.0), then `S = αV + βG + γH` uses equal weights of one third. The fallback `S = αV + γH` is documented but inactive because G was feasible to build. The TF-IDF V implementation is a sparse lexical vector baseline, not dense semantic embeddings; it should be replaced or supplemented before claiming paraphrase-level semantic retrieval.

The retrieval benchmark is recorded in `reports/retrieval_evaluation.md` and `reports/retrieval_evaluation_per_question.csv`. Macro results on the ten covered questions were V P@5 0.120, Recall@5 0.110, MRR 0.333; V+G P@5 0.060, Recall@5 0.124, MRR 0.090. The full formula has identical UEFA-page ranks because H returns a different evidence type and no page qrels exist for historical cases. H same-match exclusion passed for all 12 questions; H relevance and factual answer quality remain unmeasured. No parameters were tuned on the locked prompts.
