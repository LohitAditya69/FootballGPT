# Lap 2 — Backend work brief and prompt

## Goal

Build the FootballGPT HTTP backend against the shared [product API contract v1](product_api_contract_v1.md). Backend work can proceed in parallel with frontend planning because the contract is the shared, read-only interface.

## Strict file and change boundary

The backend worker may read the repository but may edit only:

- New files under `backend/api/`.
- A new root `requirements-api.txt` if an API dependency is needed.
- This backend brief and its Lap 2 checklist.

Treat `reports/product_api_contract_v1.md` as read-only. Do not edit frontend files, retrieval implementation, ranking configuration, source data, evidence chunks, evaluation questions, qrels, generated review labels, `README.md`, or other project files. Do not delete, rename, reformat, or regenerate existing files. If implementation needs any path outside the allowlist, stop and ask the user for approval before changing it. Report the exact path and why it is needed.

Do not tune retrieval against any v1/v2 held-out questions. Do not make claims of coach approval or factuality accuracy. Do not push. Work in a separate branch/worktree from the frontend task so file changes and commits cannot collide. A local commit may include only allowlisted backend files and this brief.

## Part 1 — Service foundation checklist

- [x] Inspect existing module interfaces and choose a small service implementation compatible with the repository; do not replace or refactor the current retrieval modules.
- [x] Add the application entry point, configuration, health route, JSON request validation, and `/api/v1/ask` route.
- [x] Map current retrieval/report outputs into the exact shared response schema.
- [x] Return explicit abstention when no adequately supported tactical passage is available.
- [x] Keep UEFA passages, recorded event evidence, historical examples, and provenance in separate fields.
- [x] Add focused backend checks under `backend/api/` for malformed input, covered/abstained cases, citation metadata, and same-match exclusion.
- [x] Record startup and local verification steps in this brief.
- [x] Review the diff and ensure every changed path is within the allowlist before committing Part 1.

## Part 2 — Reliability and provenance checklist

- [x] Validate returned evidence IDs, page numbers, and source IDs against the fixed report chunk index.
- [x] Preserve exact source excerpts and the provenance trace.
- [x] Enforce historical match exclusion whenever H is used; skip H when the query event cannot be grounded.
- [x] Represent weak/no evidence as abstention instead of returning arbitrary top-ranked passages as support.
- [x] Return structured errors with request IDs and no stack traces or sensitive internal details.
- [x] Document source coverage, missing-video limitations, and any unavailable evidence channels.
- [x] Verify the response shape for a supported question, not-covered question, invalid input, and service failure.
- [x] Review the diff for scope, update this brief, and create a local commit containing only allowlisted backend changes.

## Startup and local verification steps

### Requirements installation
```bash
pip install -r requirements-api.txt
```

### Running the server locally
```bash
# Start server using the entrypoint (default on http://127.0.0.1:8000)
python backend/api/main.py --host 127.0.0.1 --port 8000

# Or using uvicorn directly:
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

### Running test suite
```bash
# Run all 12 focused API and contract tests
pytest backend/api/test_api.py -v
```

### Running end-to-end verification script
```bash
# Exercises health, supported query, same-match exclusion, abstention, 400 validation error, and 500 service error
python backend/api/verify_service.py
```

### Example curl requests

1. Health check:
```bash
curl -X GET http://127.0.0.1:8000/health
```

2. Supported tactical question:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How should a team respond after winning the ball?"}'
```

3. Grounded query with match and trigger event context:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Sevilla intercepted Barcelona’s incomplete pass and then played to Diego Perotti. Should the first action prioritize securing possession or countering forward?", "context": {"match_id": "69289", "trigger_event_id": "a8741e2f-3aff-4a73-aacb-1ae683e6a2a1"}}'
```

4. Weak-evidence question (abstention):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Arsenal’s pass from Eduardo toward Fredrik Ljungberg is recorded after a blocked shot and goalkeeper action, and the pass outcome is marked incomplete. What should a coach verify about the possession/restart before judging the pass choice? Given the actual setup, what safer or more progressive option was available?", "context": {"match_id": "3749448", "trigger_event_id": "6cfd4b03-ddc9-4e64-8af3-d743540aea3f"}}'
```

## Copy-ready backend prompt

> Work on FootballGPT Lap 2: implement the backend service using `reports/product_api_contract_v1.md` as a read-only contract. First inspect the existing repository and Git status. Pull incoming changes if the remote is reachable; if the working tree is dirty, the pull fails, or a conflict appears, stop and report it without resetting or overwriting anything.
>
> **Edit only** new files under `backend/api/`, a new root `requirements-api.txt` if required, and `reports/backend_lap2.md`. Do not edit the shared API contract, frontend files, existing retrieval code or configuration, data/evidence/benchmark files, generated review labels, README, or other paths. Do not delete or reformat unrelated files. If the task requires any path outside this allowlist, stop and ask me before editing it.
>
> Implement Part 1 and Part 2 from the checklist in this brief. Preserve citations and exact excerpts; keep UEFA evidence, StatsBomb events, historical examples, provenance, limitations, and abstention distinct. Never imply that retrieved text is supported solely because it ranked highly. Do not tune on v1/v2 held-out questions, claim live coach approval, or push changes. Run focused checks required by this task, inspect the final diff for allowlist compliance, update only this brief, and make a local commit containing only allowlisted changes. Report changed files, verification, commit, and any blocked/out-of-scope request.

## Lap 2 status

- [x] Part 1 service foundation complete.
- [x] Part 2 reliability and provenance complete.
- [x] API contract implemented without unapproved changes.
- [x] Scope-reviewed local commit recorded.

### Review follow-up

- [x] Removed evaluation-seed gold labels and seed-derived event grounding from runtime request handling.
- [x] Use `unknown` when retrieval finds no adequately supported passage; do not infer source non-coverage from retrieval failure.
- [x] Require graph evidence score at or above the configured 0.5 threshold before it can independently support an answer.
- [x] Corrected the formatted health endpoint shown by the CLI startup message.

