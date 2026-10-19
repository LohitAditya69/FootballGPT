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

## Candidate-index size comparison

`scripts/sample_historical_dev_candidates.py` streams the original training
file and writes only cases from the 3,007 candidate matches. It leaves the
source JSONL unchanged and defaults to `/private/tmp/footballgpt_historical_candidates_v1/`
so generated match data is not accidentally added to Git. Run it with:

```bash
python3 scripts/sample_historical_dev_candidates.py
```

The deterministic samples use one hash ordering, so they are nested:

| Maximum cases per candidate match | Cases | Matches represented | Compressed size |
|---:|---:|---:|---:|
| 3 | 9,021 | 3,007 | 498,233 bytes |
| 10 | 30,070 | 3,007 | 1,585,009 bytes |
| 25 | 75,175 | 3,007 | 3,821,072 bytes |

The candidate case corpus contains five recorded trigger event types, all of
which appear in each tier: Pressure, Pass, Shot, Interception, and
Substitution. The
25-per-match sample is still small compared with all candidate cases, so a
full candidate index is technically possible but should wait until the
development evaluation shows whether broader sampling improves retrieval.
These counts and file sizes establish coverage and storage cost only; they do
not show that the larger sample retrieves more relevant situations. The
generated sample summary records SHA-256 hashes for the three local files.
