# Project status, limitations, and contribution record

## Pipeline status

- **V/G/H retrieval:** implemented. V uses sparse TF-IDF or BM25, G uses curated concept links, and H retrieves train-split event situations while excluding the query match.
- **Retrieval evaluation:** v1 and v2 reports are saved under `reports/`. V2 has 42 development questions and 20 new held-out questions with page-disjoint targets. The selected BM25+G configuration raises held-out MRR slightly over fixed BM25 (0.292 vs 0.275) but has lower P@5 and Recall@5 (0.080/0.400 vs 0.090/0.450). This is a mixed pilot result, not a demonstrated overall improvement.
- **Answer output:** `scripts/generate_grounded_reports.py` creates 12 evidence briefs. Ten provide verbatim report passages with page citations; two annotated `not_covered` questions abstain. Recorded StatsBomb windows are shown separately from tactical text.
- **Provenance and browser view:** each brief carries an RGG graph linking the question to retrieved page chunks and its event window. `reports/generated/index.html` renders the briefs, passages, event records, and provenance edges.
- **Factuality review:** `reports/generated/factuality_review.csv` contains 30 passage-review rows and two abstention-review rows. Reviewer fields are blank. No factuality score or coach approval is claimed until a qualified reviewer completes this sheet.
- **Lap 1 reliability audit:** all five report hashes, 30 excerpt-to-chunk citations, 12 raw StatsBomb windows (132 event records), 12 provenance traces, and two abstentions passed integrity checks. Only 3/30 generated citations match the locked target pages, across 2/10 covered questions; this is a retrieval-alignment diagnostic, not a judgment that the other excerpts are false. See `reports/reliability_review_lap1.md`.

## Limitations and next review

The UEFA reference questions and page labels are a small, AI-drafted pilot, not independent coach judgments. A single target page per question can omit other relevant passages. The Lap 1 audit found a low exact target-page rate among displayed generated citations (3/30); this signals an alignment problem against the locked labels and does not establish that every other excerpt is factually false. BM25 and TF-IDF are sparse lexical methods; curated graph aliases can miss paraphrases or match irrelevant context. Historical-case relevance has no judged qrels, so its fusion weight has not been evaluated against relevance labels.

The answer generator quotes retrieved passages instead of synthesizing tactical recommendations. StatsBomb event windows provide recorded events only; they cannot establish team shape, off-ball runs, or the video context needed to make conditional coaching decisions. The generated review sheet is a human-review instrument, not an automated factuality metric. The held-out v2 questions must not be used for further tuning.

Before making stronger answer-quality claims, have independent football reviewers assess the passage support and abstentions, record disagreements, and evaluate on a larger held-out set with broader page relevance judgments. Consider a separately validated dense retriever only after establishing that evaluation set.

## Contribution summary from Git history

This summary attributes work by commit subject and author metadata; it is not an independently verified allocation of effort.

| Git author | Contributions visible in commit history |
|---|---|
| LohitAditya69 | Initial StatsBomb and SoccerNet ingestion pipelines. |
| Hariharan | StatsBomb tactical case pipeline and the GGTR development merge. |
| Sriram | Initial repository work, evidence retrieval pipeline, retrieval benchmark v2, and grounded report/provenance pipeline. |

## Reproducibility

Regenerate the report and provenance artifacts with:

```bash
./.venv/bin/python scripts/generate_grounded_reports.py
```

The script expects the checked-in evidence graph, BM25 index, historical train sample, frozen question CSV, and prepared StatsBomb event windows. It writes the JSONL reports, JSONL provenance, blank factuality review CSV, and static browser view under `reports/generated/`.
