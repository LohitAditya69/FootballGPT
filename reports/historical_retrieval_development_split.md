# Historical retrieval development split

## Purpose

Reserve whole matches from the original training set for developing and
evaluating historical-situation retrieval (**H**). Every query match must be
excluded from its candidate set so nearby events from the same match cannot
inflate retrieval scores.

## Split

- Source: `cases_output_full/train.jsonl`, read-only.
- Rows scanned: 1,759,328.
- Unique original-training matches: 3,341.
- Development-query matches: 334 (10% rounded to the nearest whole match).
- Candidate matches: 3,007.
- Match overlap: 0; the two ID lists form a complete partition of the original
  training match IDs.
- The original `cases_output_full/test.jsonl` was not read or modified. The
  existing case-corpus audit documents that original train and test match IDs
  are disjoint.

The deterministic assignment sorts IDs by SHA-256 of the fixed namespace and
match ID, then reserves the first 10% for development. The exact match IDs and
assignment metadata are in `historical_retrieval_match_split_v1.json`.

Recreate the manifest from the same unchanged input with:

```bash
python3 scripts/create_historical_dev_split.py
```

The script verifies the row and match counts recorded in
`case_corpus_audit.md` before writing. It only writes the small manifest; it
does not edit or copy any source dataset files. Do not regenerate this split
after looking at retrieval results. A changed split must receive a new version
and its own evaluation record.

## Evaluation guardrails

- Build historical candidates only from the 3,007 candidate match IDs.
- Use query situations only from the 334 development-query match IDs.
- Never allow any case from a query match into its candidate index.
- Do not use the original held-out test questions to tune historical weights.
- The current similarity features describe recorded StatsBomb metadata. A
  match on event type, play pattern, location, outcome, pressure, or
  counterpress does not establish that two situations are tactically equivalent.
- This split provides query/candidate separation, not relevance labels. The
  next step must define and document the event-similarity criteria before
  reporting H metrics.
