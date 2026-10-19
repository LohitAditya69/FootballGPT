# FootballGPT product API contract v1

**Status:** Shared draft for Lap 2 backend and Lap 3 frontend planning. Treat this file as read-only during implementation. Any contract change must be reviewed and approved by the user before either side implements it.

## Endpoint

`POST /api/v1/ask`

Request and response bodies use JSON. A successful request returns HTTP 200, including when the system abstains. Invalid input returns HTTP 400; an unexpected service failure returns HTTP 500.

## Request

```json
{
  "question": "How should a team respond after winning the ball?",
  "context": {
    "match_id": "optional StatsBomb match ID",
    "trigger_event_id": "optional StatsBomb event UUID"
  }
}
```

- `question` is required, trimmed, and must contain 1–2000 characters.
- `context` is optional. `match_id` and `trigger_event_id` are optional strings. The backend must not invent event context. If a query event cannot be resolved, it must skip historical retrieval and state that limitation. When historical retrieval runs, it must exclude `match_id` from its candidate results.

## Successful response

```json
{
  "schema_version": "footballgpt-response-v1",
  "request_id": "server-generated ID",
  "status": "answered",
  "support_status": "conditional",
  "answer_mode": "extractive_evidence_brief",
  "answer": "Evidence summary or abstention explanation.",
  "tactical_passages": [
    {
      "evidence_id": "uefa-ucl-2024-25:p90:c1",
      "source_id": "uefa-ucl-2024-25",
      "source_title": "UEFA Champions League 2024/25 Technical Report",
      "page": 90,
      "citation": "uefa-ucl-2024-25 p.90",
      "excerpt": "Exact source passage.",
      "score": 0.72
    }
  ],
  "event_evidence": {
    "evidence_id": "statsbomb:match:event",
    "match_id": "match ID",
    "trigger_event_id": "event UUID",
    "trigger_event_type": "Interception",
    "trigger_timestamp": "00:03:16.834",
    "window_rule": "Description of the event window",
    "events": []
  },
  "historical_examples": [],
  "provenance": {
    "schema_version": "rgg-provenance-v1",
    "question_id": "optional ID",
    "nodes": [],
    "edges": []
  },
  "limitations": []
}
```

- `status` is `answered` or `abstained`.
- `support_status` is `conditional`, `not_covered`, or `unknown`.
- `answer_mode` is `extractive_evidence_brief` or `abstain`.
- For abstention, return `status: "abstained"`, `answer_mode: "abstain"`, an explanatory `answer`, and an empty `tactical_passages` array.
- Each tactical passage must preserve the source ID, page, stable evidence ID, citation string, and exact excerpt. Do not label a retrieved passage as relevant merely because it was retrieved.
- `event_evidence` may be `null` when no supported event window is available. Keep recorded match events distinct from UEFA tactical passages.
- `historical_examples` may be empty. If populated, label them as historical event examples, not UEFA principles or coaching ground truth.
- `provenance` may be `null` only when no provenance can be produced; explain the omission in `limitations`.
- `limitations` must state material source coverage or missing-video constraints where applicable.

## Error response

```json
{
  "schema_version": "footballgpt-error-v1",
  "request_id": "server-generated ID",
  "error": {
    "code": "invalid_request",
    "message": "Question must contain 1–2000 characters."
  }
}
```

Errors must not expose stack traces, file paths, secrets, or raw internal exception text.

## Evidence and quality rules

- Return only citations that resolve to the fixed UEFA chunk index and whose page/source metadata agrees with that index.
- Do not promise that a passage supports the question solely because it ranked highly. If no adequately supported passage is available, abstain.
- Keep StatsBomb event records and historical examples separate from tactical principles.
- Event data does not establish off-ball runs, team shape, or unseen video context.
- Do not tune ranking, prompts, thresholds, or labels against the v1/v2 held-out questions. Retrieval improvement belongs on development data and must be documented separately.

## Ownership

This shared contract is jointly consumed but not owned by either implementation lap. Backend and frontend prompts may read it but may not edit it. If implementation requires a change, stop, describe the mismatch, and request user approval before changing this file or adding an incompatible field.
