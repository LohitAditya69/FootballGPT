# Case Corpus Audit

## Split integrity

- Train rows scanned: 1,759,328
- Test rows scanned: 454,339
- Unique train match IDs: 3,341
- Unique test match IDs: 860
- Match IDs in both splits: 0
- Missing case IDs: 0
- Missing match IDs: 0
- Raw StatsBomb matches with no cases: 34
- Event files containing the 96-byte rate-limit error: 34
- Lineup files containing the 96-byte rate-limit error: 2
- Valid raw matches without cases: 0
- Case match IDs absent from raw event files: 0

| Count | Scanned | summary.json | result |
|---|---:|---:|---|
| train | 1,759,328 | 1,759,328 | match |
| test | 454,339 | 454,339 | match |
| total | 2,213,667 | 2,213,667 | match |

Conclusion: no match leakage found; each match is confined to one split.

## Sample review

- Created 12 deterministic, stratified seed rows from the held-out test split.
- Frequent train event types:
- Pressure: 1,100,480
- Pass: 474,691
- Shot: 85,760
- Interception: 76,298
- Substitution: 22,099
- Frequent test event types:
- Pressure: 282,960
- Pass: 124,830
- Shot: 21,633
- Interception: 19,249
- Substitution: 5,667
- Frequent test field zones:
- attacking_third: 177,513
- middle_third: 173,158
- defensive_third: 98,001
- unknown: 5,667
- Frequent test phases:
- settled_possession: 220,345
- defensive_transition: 190,011
- final_third_attack: 43,983

All 12 seed trigger events were matched to the raw StatsBomb event ID, type, and timestamp. Phase and field-zone values are case-builder heuristics. Candidate actions are generated heuristics, not verified facts or expert answers.

## Question-set status

The question CSV is `/Users/mac/Desktop/Sem_5/NLP/FootballGPT/reports/evaluation_seed_questions.csv`. It contains original and frozen revised wording, static reference answers, UEFA report/page qrels where supported, StatsBomb event references, and explicit `conditional` or `not_covered` labels. All 12 questions are from the held-out test split. The exact five UEFA reports are hash-locked in `reports/uefa_report_manifest.json`; scope and metrics are fixed in `reports/evaluation_scope_lock.md`.

Ten questions have conditional support in the UEFA Technical Observer reports; two event-context questions are explicitly not covered by those reports and are evaluated for source-aware abstention/uncertainty. Match-specific facts remain grounded in StatsBomb events. No live coach review is used or claimed.

## Split implementation

The current case-builder code assigns splits using a stable hash of match_id. This audit scanned the saved train and test files to verify the persisted corpus directly.

Invalid raw event files containing the service error (first 50 of 34): 3911545, 3911558, 3911630, 3913073, 3913079, 3913081, 3913086, 3913119, 3913134, 3913148, 3913163, 3920388, 3920408, 3920416, 3922239, 3922242, 3928985, 3928992, 3928998, 3929002, 3929022, 3929023, 3930163, 3930168, 3930170, 3930183, 3938639, 3938641, 3939969, 69162, 69278, 70281, 70301, 7532

Invalid lineup file IDs: 3754241, 3901144
