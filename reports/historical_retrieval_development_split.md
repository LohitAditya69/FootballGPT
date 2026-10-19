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
  project-defined metadata-similarity rubric below supplies a reproducible
  proxy for the next development evaluation; it is not coach-judged tactical
  relevance.

## Similarity definition v1

The historical task is **retrieval of metadata-similar recorded situations**.
It is not a claim that two events are tactically equivalent, that one outcome
was caused by the other event's context, or that one situation recommends an
action. The query and candidate fields are taken from the existing StatsBomb-
derived case records. StatsBomb locations use a 120-by-80 pitch coordinate
frame ([StatsBomb Open Data specification](https://github.com/statsbomb/open-data/blob/master/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf)).

### Development relevance grades

Apply these rules to each development query and every case in the fixed
25-per-match reference sample, excluding the query match:

- **Grade 2 — close metadata analogue:** same `event_type` and same
  `play_pattern` after case-folding (both values present), and normalized
  Euclidean location distance at most `0.10`.
- **Grade 1 — partial metadata analogue:** same `event_type` after
  case-folding and either the same `play_pattern` after case-folding (both
  present) or normalized location distance at most `0.15`, but not grade 2.
- **Grade 0 — not a metadata analogue:** event types differ, or the same event
  type has neither a matching play pattern nor location within `0.15`.
- **Ungraded:** query/candidate `event_type` is missing, or both compared
  `play_pattern` cannot be compared and location is unavailable. Exclude
  ungraded pairs from the relevant-count and ideal-DCG denominators; count
  them as unconfirmed non-relevant if they appear in a top-five result, and
  report their count separately.

Normalized location distance is
`sqrt(((xq-xc)/120)^2 + ((yq-yc)/80)^2)` using recorded coordinates. The
`0.10` and `0.15` cutoffs are project-defined thresholds, not established
football standards. Freeze them for this split before calculating retrieval
metrics.

### Ranking and interpretation

Keep the existing historical ranker unchanged for the first comparison:
event type `0.40`, play pattern `0.15`, location `0.25`, event outcome `0.10`,
under-pressure `0.05`, and counterpress `0.05`; renormalize over fields
available for both records. The relevance grades intentionally do not use
outcome, pressure, or counterpress. This allows the comparison to ask whether
the current complete score ranks cases that satisfy the simpler event-type,
play-pattern, and location rubric.

These are automatically derivable labels from recorded metadata. Report H
metrics as agreement with this explicit proxy only, not as human-judged
relevance or tactical effectiveness. Compare the 3-, 10-, and 25-per-match
indices against the same query cases and the same 25-per-match reference-pool
relevance set; do not define labels separately within each sample. This is a
sampled reference pool, not a complete set of all candidate training cases.
Keep the original v1/v2 held-out questions and matches out of tuning.

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
Substitution. The 25-per-match sample is still small compared with all
candidate cases, so a full candidate index is technically possible. The
current metadata-proxy results are too self-confirming to justify that
expansion. These counts and file sizes establish coverage and storage cost
only; they do not show that the larger sample retrieves more tactically useful
situations. The generated sample summary records SHA-256 hashes for the three
local files.

## Development-only sample comparison

`scripts/evaluate_historical_dev_samples.py` selects one deterministic query
case from each of the 334 reserved development matches, with event types
balanced by deterministic rotation. It evaluates the unchanged H scorer at
`k=5`. The fixed relevance reference pool is the 25-per-match candidate sample
(75,175 cases); labels are not recomputed separately for the smaller indexes.
Query cases and detailed per-query output are written under
`/private/tmp/footballgpt_historical_evaluation_v1/` and are not source data or
Git-tracked benchmark files.

Recreate the development comparison after sampling with:

```bash
python3 scripts/evaluate_historical_dev_samples.py
```

The 334-query event-type counts were 58 Interception, 71 Pass, 68 Pressure,
65 Shot, and 72 Substitution.

| Candidate sample | P@5 | Recall@5 | MRR@5 | nDCG@5 |
|---:|---:|---:|---:|---:|
| 3 per match | 0.994 | 0.010 | 1.000 | 0.898 |
| 10 per match | 0.999 | 0.013 | 1.000 | 0.952 |
| 25 per match | 1.000 | 0.014 | 1.000 | 0.978 |

All 334 queries had at least one positive under the metadata rubric. However,
the 25-per-match reference pool labels a mean of about 8,516 cases per query as
relevant (median 2,181; range 6–24,517); Pass queries have exactly 20,340
positive cases each.
The grade rule and H ranker both use event type, play pattern, and location.
This overlap, together with the broad positive sets, makes the high P@5/MRR
near-ceiling and the scores self-confirming. The small increases across sample
sizes show better agreement with this proxy as more examples are indexed; they
do **not** establish better tactical retrieval. Do not pick the production
index size or change H weights based on these numbers.

This is a reproducibility and metadata-proxy diagnostic only. It does not
replace independently judged relevance. Since this project does not claim
live coach review, any future relevance labels must be separately sourced and
described accurately; otherwise report only metadata-proxy metrics and do not
claim tactical effectiveness.
