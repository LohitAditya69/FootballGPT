# Lap 3 — Frontend work brief and prompt

## Goal

Build the FootballGPT frontend against the shared, read-only [product API contract v1](product_api_contract_v1.md). Frontend work can proceed in parallel with the backend because the interface contract is defined independently.

## Strict file and change boundary

The frontend worker may read the repository but may edit only:

- New files under `frontend/` (including its own package manifest, lockfile, source, and assets).
- This frontend brief and its Lap 3 checklist.

Treat `reports/product_api_contract_v1.md` as read-only. Do not edit backend files, retrieval implementation, ranking configuration, source data, evidence chunks, evaluation questions, qrels, generated review labels, `README.md`, or other project files. Do not delete, rename, reformat, or regenerate existing files. If implementation needs any path outside the allowlist, stop and ask the user for approval before changing it. Report the exact path and why it is needed.

Do not tune retrieval against v1/v2 held-out questions. Do not claim coach approval or imply that event data proves unseen video context. Do not push. Work in a separate branch/worktree from the backend task so file changes and commits cannot collide. A local commit may include only allowlisted frontend files and this brief.

## Part 1 — Interface foundation checklist

- [ ] Inspect the current project and choose a frontend stack contained entirely under `frontend/`; do not add root-level tooling or change existing project configuration.
- [ ] Build a question-entry and result-view shell using API-contract-shaped sample data.
- [ ] Show loading, empty, invalid-input, service-error, and abstention states.
- [ ] Display UEFA citations and excerpts separately from StatsBomb event records and historical examples.
- [ ] Display provenance and limitations without implying a coach recommendation or human review.
- [ ] Check desktop and narrow viewport layouts and basic keyboard access.
- [ ] Document local startup and the expected API base URL in this brief.
- [ ] Review the diff and ensure every changed path is within the allowlist before committing Part 1.

## Part 2 — Live evidence and provenance checklist

- [ ] Connect the question form to `POST /api/v1/ask` as defined by the shared contract.
- [ ] Render clickable source/page citations and the exact returned excerpts.
- [ ] Keep tactical passages, event records, historical examples, and provenance visibly distinct.
- [ ] Render abstention and missing-source states without showing unsupported passages as evidence.
- [ ] Handle structured API errors and malformed/missing fields safely.
- [ ] Verify one supported response, one abstention, and one service error against the backend when it is available.
- [ ] Review the diff for scope, update this brief, and create a local commit containing only allowlisted frontend changes.

## Copy-ready frontend prompt

> Work on FootballGPT Lap 3: implement the frontend against `reports/product_api_contract_v1.md` as a read-only contract. First inspect the existing repository and Git status. Pull incoming changes if the remote is reachable; if the working tree is dirty, the pull fails, or a conflict appears, stop and report it without resetting or overwriting anything.
>
> **Edit only** new files under `frontend/` and `reports/frontend_lap3.md`. Do not edit the shared API contract, backend files, retrieval code/configuration, data/evidence/benchmark files, generated review labels, README, or other paths. Do not delete or reformat unrelated files. If you need a change outside this allowlist, stop and ask me before editing it.
>
> Implement Part 1 and Part 2 from this brief. Keep citations, StatsBomb events, historical examples, provenance, limitations, and abstentions distinct. Do not imply that a passage is relevant solely because the backend returned it, do not claim human coach review, and do not infer unseen video context. Do not tune on v1/v2 held-out questions or push changes. Run focused checks required by this task, inspect the final diff for allowlist compliance, update only this brief, and make a local commit containing only allowlisted changes. Report changed files, verification, commit, and any blocked/out-of-scope request.

## Lap 3 status

- [ ] Part 1 interface foundation complete.
- [ ] Part 2 live evidence and provenance complete.
- [ ] Integration against the approved API contract complete.
- [ ] Scope-reviewed local commit recorded.
