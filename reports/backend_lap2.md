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

- [ ] Inspect existing module interfaces and choose a small service implementation compatible with the repository; do not replace or refactor the current retrieval modules.
- [ ] Add the application entry point, configuration, health route, JSON request validation, and `/api/v1/ask` route.
- [ ] Map current retrieval/report outputs into the exact shared response schema.
- [ ] Return explicit abstention when no adequately supported tactical passage is available.
- [ ] Keep UEFA passages, recorded event evidence, historical examples, and provenance in separate fields.
- [ ] Add focused backend checks under `backend/api/` for malformed input, covered/abstained cases, citation metadata, and same-match exclusion.
- [ ] Record startup and local verification steps in this brief.
- [ ] Review the diff and ensure every changed path is within the allowlist before committing Part 1.

## Part 2 — Reliability and provenance checklist

- [ ] Validate returned evidence IDs, page numbers, and source IDs against the fixed report chunk index.
- [ ] Preserve exact source excerpts and the provenance trace.
- [ ] Enforce historical match exclusion whenever H is used; skip H when the query event cannot be grounded.
- [ ] Represent weak/no evidence as abstention instead of returning arbitrary top-ranked passages as support.
- [ ] Return structured errors with request IDs and no stack traces or sensitive internal details.
- [ ] Document source coverage, missing-video limitations, and any unavailable evidence channels.
- [ ] Verify the response shape for a supported question, not-covered question, invalid input, and service failure.
- [ ] Review the diff for scope, update this brief, and create a local commit containing only allowlisted backend changes.

## Copy-ready backend prompt

> Work on FootballGPT Lap 2: implement the backend service using `reports/product_api_contract_v1.md` as a read-only contract. First inspect the existing repository and Git status. Pull incoming changes if the remote is reachable; if the working tree is dirty, the pull fails, or a conflict appears, stop and report it without resetting or overwriting anything.
>
> **Edit only** new files under `backend/api/`, a new root `requirements-api.txt` if required, and `reports/backend_lap2.md`. Do not edit the shared API contract, frontend files, existing retrieval code or configuration, data/evidence/benchmark files, generated review labels, README, or other paths. Do not delete or reformat unrelated files. If the task requires any path outside this allowlist, stop and ask me before editing it.
>
> Implement Part 1 and Part 2 from the checklist in this brief. Preserve citations and exact excerpts; keep UEFA evidence, StatsBomb events, historical examples, provenance, limitations, and abstention distinct. Never imply that retrieved text is supported solely because it ranked highly. Do not tune on v1/v2 held-out questions, claim live coach approval, or push changes. Run focused checks required by this task, inspect the final diff for allowlist compliance, update only this brief, and make a local commit containing only allowlisted changes. Report changed files, verification, commit, and any blocked/out-of-scope request.

## Lap 2 status

- [ ] Part 1 service foundation complete.
- [ ] Part 2 reliability and provenance complete.
- [ ] API contract implemented without unapproved changes.
- [ ] Scope-reviewed local commit recorded.
