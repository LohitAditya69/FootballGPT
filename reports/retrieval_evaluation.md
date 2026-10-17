# Locked retrieval evaluation

Benchmark v1: evaluated the original 12 frozen prompts against the locked report-page qrels using BM25 `k1=2.0`, `b=0.5`, and a 0.7:0.3 V:G ratio. These settings are archived in `backend/retrieval/ranking_config_v1.json`. No settings were tuned on these questions.

## Macro results on the 10 UEFA-covered questions

| Page-ranking mode | P@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| V (TF-IDF baseline) | 0.120 | 0.110 | 0.333 |
| V (BM25 baseline, k1=1.5, b=0.75) | 0.140 | 0.122 | 0.300 |
| TF-IDF+G (equal weights) | 0.060 | 0.124 | 0.090 |
| BM25+G (equal weights) | 0.020 | 0.100 | 0.050 |
| Selected BM25+G (dev-tuned relative weight) | 0.120 | 0.111 | 0.267 |
| Full configuration, UEFA-page candidate pool | 0.120 | 0.111 | 0.267 |

Metrics use distinct report pages, ranked by the best chunk score on each page. `P@5` divides by 5; `Recall@5` uses all locked relevant pages for that question; MRR uses the first relevant page. Macro means cover the ten questions with conditional UEFA support.

## Interpretation and limits

- BM25 is a sparse lexical ranking method, not dense embedding semantics. The selected k1/b and V:G relative weight were tuned only on the separate 22-question development set, then frozen before this locked evaluation.
- For UEFA-page metrics, H has no page-level relevance labels and returns a different item type (historical match cases). The full-configuration page row therefore projects the frozen αV+βG weights onto UEFA chunks; γH is absent for each page. This does not measure H relevance or the quality of a mixed-source top-five list.
- H same-match exclusion: passed for all 12 queries. Historical relevance is unjudged because the locked qrels contain no similar-match labels.
- Two not-covered questions are reported separately; lexical and graph retrieval returned no UEFA pages for 0 of 2. The system has no explicit calibrated abstention threshold, so this is a no-result check, not a validated abstention score.
- The selected development setting performs below fixed BM25 on all three locked metrics. This indicates poor development-to-test transfer; the locked set was not used to retune or choose a replacement.
- This is a 12-question pilot. Report results descriptively; do not infer broad generalization.

## Per-question results

See `reports/retrieval_evaluation_per_question.csv` for every question’s metrics, top-five pages, H top match, and same-match exclusion result.

No answer generation or factuality scoring was run in this step.
