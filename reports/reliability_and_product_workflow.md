# Reliability and product build workflow

## Working rules

- Keep the existing v1 and v2 held-out questions separate from development data. Do not tune retrieval, prompts, or thresholds against held-out results.
- Treat the frozen UEFA reports and recorded StatsBomb events as the factual reference. A source audit checks whether claims and citations match those records; it does not claim live coach approval or unseen video context.
- Build backend and frontend against one written API contract. Keep backend work in Lap 2 and frontend work in Lap 3; each gets two parts and an integration checkpoint.
- At the start of each lap, check the Git branch and working tree and pull incoming changes when the remote is reachable. At the end, update this file and the relevant README/status docs, run the lap's verification, and commit that lap before starting the next.
- Never overwrite or discard another person's changes. If a pull conflicts or the working tree is not clean, stop and reconcile before editing.

## Lap 1 — Reliability review

### 1A. Audit benchmark and labels

- [x] Confirm all v1/v2 questions map to existing pages in the frozen report corpus or are explicitly marked not covered.
- [x] Check question, split, report ID, page number, and report hash consistency.
- [x] Review the 42 development questions for duplicate intent, overly report-specific wording, and target-page omissions.
- [x] Preserve v2 held-out labels and results unchanged; record any discovered annotation issue as a new benchmark version rather than silently editing v2.
- [x] Reconfirm historical retrieval excludes each query match and state clearly that historical relevance has no judged qrels.

### 1B. Audit generated evidence and risks

- [x] For each of the 12 generated briefs, verify every quoted UEFA passage against its cited page.
- [x] Verify every match statement against the corresponding recorded StatsBomb event window.
- [x] Confirm the two not-covered questions abstain and do not present retrieved passages as support.
- [x] Check that the provenance JSON links each displayed citation to its retrieved chunk and keeps event evidence distinct from tactical principles.
- [x] Keep missing-video limitations explicit: event data does not prove off-ball runs, team shape, or nearby options.
- [x] Update the reliability findings, unresolved issues, README, and completion status before product work begins.

### Lap 1 exit criteria

- [x] Reliability report lists reviewed artifacts, checks performed, findings, and unresolved limitations.
- [x] No held-out labels or scores were changed or used for tuning.
- [x] The API fields needed to expose citations, event evidence, abstention, and provenance are agreed and recorded for Lap 2.

## Lap 2 — Backend

Backend scope, checklist, and copy-ready prompt: [`backend_lap2.md`](backend_lap2.md). Shared read-only API contract: [`product_api_contract_v1.md`](product_api_contract_v1.md).

### 2A. Agree and freeze the interface contract

- [x] Define request fields: question and optional match/event context.
- [x] Define response fields: evidence brief, citations, recorded event evidence, historical examples, provenance, abstention status, limitations, and structured errors.
- [x] Define citation identity and page numbering once so backend and frontend use the same form.
- [x] Save the shared contract in `product_api_contract_v1.md`; treat it as read-only for both implementation laps.

### 2B. Backend — Part 1: service foundation

- [ ] Add the application entry point, configuration, health endpoint, and request validation.
- [ ] Wire the frozen retrieval pipeline to the service using the selected local index and configured sources.
- [ ] Return structured response data matching the agreed contract; keep tactical text separate from StatsBomb facts.
- [ ] Return an explicit abstention when no supported evidence is available.
- [ ] Add focused backend checks for malformed input, missing evidence, citations, and match-exclusion behavior.

### 2C. Backend integration checkpoint

- [ ] Run the backend locally and confirm its response matches the contract.
- [ ] Exercise one supported request and one abstention through the service interface or a contract client.
- [ ] Resolve contract mismatches before completing backend reliability work.
- [ ] Update docs and commit the backend foundation checkpoint.

### 2D. Backend — Part 2: reliability and provenance

- [ ] Validate citation IDs and page references against the fixed report index before returning them.
- [ ] Preserve source excerpts and provenance links in the response.
- [ ] Enforce the same-match exclusion for historical examples.
- [ ] Record useful errors and request IDs without logging unnecessary sensitive input.
- [ ] Document any fallback behavior and source coverage limits.

### 2E. Backend exit checkpoint

- [ ] Verify final API responses for covered, not-covered, invalid-input, and failure cases.
- [ ] Freeze/version the API contract and document local startup instructions for the frontend lap.
- [ ] Update README and workflow status, then commit Lap 2 before starting Lap 3.

## Lap 3 — Frontend

Frontend scope, checklist, and copy-ready prompt: [`frontend_lap3.md`](frontend_lap3.md). Work only in a separate branch/worktree from Lap 2 and treat the shared API contract as read-only.

### 3A. Frontend — Part 1: interface foundation

- [ ] Read the versioned Lap 2 API contract and build the question-entry and result-view shell using sample responses.
- [ ] Show loading, empty, error, and abstention states.
- [ ] Make report citations and recorded match evidence visually distinct.
- [ ] Check the layout at desktop and narrow viewport sizes.
- [ ] Commit the interface foundation before connecting live responses.

### 3B. Frontend integration checkpoint 1

- [ ] Start the backend using its documented instructions and connect the frontend to it.
- [ ] Verify one supported question and one abstention against the actual API.
- [ ] Resolve contract mismatches with a versioned backend contract change before relying on new fields.
- [ ] Update docs and commit the first integration checkpoint.

### 3C. Frontend — Part 2: live evidence and provenance

- [ ] Connect the question form to the live backend response.
- [ ] Render clickable report/page citations and the exact supporting excerpts.
- [ ] Render StatsBomb event records separately from UEFA tactical evidence.
- [ ] Expose the provenance path in a readable expandable view.
- [ ] Display abstention and coverage limits without implying unsupported recommendations.

### 3D. Integration checkpoint 2 and delivery review

- [ ] Run an end-to-end flow from question entry through API response to cited evidence display.
- [ ] Check covered and not-covered cases, service errors, and missing/invalid citation behavior.
- [ ] Confirm no held-out question was used to tune the live system.
- [ ] Update README, this workflow, and project status with completed items and remaining risks.
- [ ] Commit the integrated result and report the branch/commit state.

## Git checkpoint record

| Checkpoint | Pull status | Commit | Notes |
|---|---|---|---|
| Workflow plan | Pull attempted on 2026-10-19 and retried before Lap 3 split; both blocked because `github.com` could not be resolved | `8d2bc6c` | Local workflow plan committed; one commit ahead of `origin/codex/pipeline-laps`. Retry pull/push when network access is available. |
| Lap 1 reliability review | Pull attempted at Lap 1 start; blocked because `github.com` could not be resolved | Lap 1 completion commit (local) | Review results are in `reliability_review_lap1.md`; preserve held-out data and address retrieval alignment using development data. |
| Backend/frontend work briefs | Pull attempted before drafting; blocked because `github.com` could not be resolved | Planning docs commit (local) | Separate prompts and edit allowlists are in `backend_lap2.md` and `frontend_lap3.md`; shared contract is in `product_api_contract_v1.md`. |

## Current status

- [x] Workflow and lap checklist written.
- [x] Lap 1 reliability review; findings and remaining risks are recorded in `reports/reliability_review_lap1.md`.
- [x] Separate backend and frontend work briefs, prompts, file allowlists, and shared API contract drafted.
- [ ] Lap 2 backend build and versioned API contract.
- [ ] Lap 3 frontend build and integration.
- [ ] Git remote synchronization; pull remains blocked by DNS/network availability.
