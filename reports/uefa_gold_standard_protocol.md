# UEFA fixed-reference protocol

The fixed corpus is `UEFA Reports/`, with five reports listed and hashed in `uefa_report_manifest.json`: Champions League, Women’s Champions League, Europa League, and Conference League 2024/25, plus Women’s EURO 2025. The exact files are the reference set; replacing any file requires a new version.

These are UEFA Technical Observer reports with static tactical analyses, annotated examples, statistics, and coaching insights. They are not question-answer manuals with pre-labeled gold answers. The project’s page-level annotations in `evaluation_seed_questions.csv` operationalize them as the fixed reference standard; no live coach review is used.

## Evidence rules

- Use cited UEFA report pages for general tactical principles and observer analyses.
- Use cited StatsBomb events for teams, event types, timestamps, pass/shot outcomes, and other match facts.
- Mark a question `not_covered` when the reports do not support its requested tactical claim. Do not force a citation.
- Keep answers conditional when the report supports a principle but the exact match frame lacks teammate, opponent, or tracking context.
- Do not treat case-builder phase, zone, or candidate-action heuristics as ground truth.

## Evaluation lock

See `evaluation_scope_lock.md` for the frozen 12 prompts, qrels, answer criteria, metrics, baselines, no-leak rule for historical retrieval, and pilot-size limitation.
