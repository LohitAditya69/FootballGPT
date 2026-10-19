# Lap 1 reliability review

**Review date:** 2026-10-19  
**Scope:** Frozen question/evidence annotations, source integrity, generated evidence briefs, StatsBomb windows, and RGG provenance.  
**Review method:** Reproducible local checks plus an AI coach-style tactical relevance review against the locked report-page labels. This is not an independent human coach review.

## Findings

### Benchmark and source integrity

- All five report PDFs exist and match their SHA-256 values in `uefa_report_manifest.json`.
- The frozen v1 seed file contains 12 test questions. Generated briefs, provenance traces, and event windows each contain exactly those 12 IDs.
- The v2 benchmark validator passed: 20 development and 20 held-out questions, valid source pages, and held-out pages disjoint from v1 labels and development pages.
- All 42 development prompts across the 22-question v1 development file and 20-question v2 development split were read for near-duplicate intent and overfitting to named teams. No exact duplicate prompts were found. Pressing/counter-pressure and mid-block themes recur intentionally across different competitions and page targets; label completeness still cannot be established from these AI-drafted questions alone.
- The review did not edit any prompts, page labels, split assignments, or benchmark scores.

### Generated citations and retrieval relevance

- All 30 displayed UEFA excerpts are exact sentences from their cited evidence chunks. Citation IDs, source/page citations, and retrieved-support provenance edges agree.
- Against the locked `gold_qrel_pages` labels, 3 of 30 displayed citations land on an annotated target page. Those hits occur in 2 of the 10 questions marked `conditional`; the other 8 have no displayed citation on a labeled target page.
- This is a benchmark-alignment result, not a claim that the remaining 27 excerpts are false. The page labels are intentionally narrow and may omit other useful pages. However, the coach-style review found several excerpts tangential or too fragmentary to support the question well. Examples include a sentence fragment (“the pitch.”), a counter-pressure statistics table for a pressing-coordination question, goalkeeper technique for a shot-choice question, and a set-piece page for a mid-block question.
- The excerpts that were tactically on-topic included transition principles for the regain questions (Q3), pressing principles for Q7–Q9, a third-player combination example for build-up (Q4), and a high-regain shot example for Q10. Other excerpts in those same briefs were weaker or unrelated. Retrieval quality therefore varies within a brief; showing three passages without a relevance threshold can make a mixed set look uniformly supportive.
- The current generator displays up to three top-ranked excerpts without a minimum relevance threshold. It also takes the first sentence from a chunk, which can produce an uninformative fragment. This makes retrieval quality and excerpt selection the main unresolved reliability risks.

### Match evidence, abstention, and provenance

- All 12 report event windows match the selected records reconstructed from the corresponding raw StatsBomb match files: 132 event records checked in total, with every trigger present.
- The event-based wording in the 12 question prompts was checked against those windows, including the linked passer/receiver, event order, shot xG/outcome, and the stated pressure-distance caveats. For example, the two low-xG shots and the saved Ryan Mason shot match the raw shot records; the two prompts explicitly marked not-covered remain event-context questions rather than UEFA-supported tactical conclusions.
- Both `not_covered` questions abstain and display no UEFA tactical passages.
- All 12 provenance graphs connect the question to each displayed citation and to its separate StatsBomb event window.
- For each of the 12 query matches, the top-100 historical retrieval output contains no candidate from that same match. The retriever requires `exclude_match_id` and removes those candidates before ranking.
- StatsBomb event records support recorded actions and metadata only. They do not establish team shape, off-ball movement, or unseen video context.

### Review-sheet status and claims

- `reports/generated/factuality_review.csv` has 32 rows (30 passage rows and two abstention rows); all reviewer decision, support type, and notes fields remain blank.
- No factuality score, independent human review, or live coach approval is claimed. The checks above establish source/provenance integrity and diagnose retrieval alignment; they do not prove that the system gives sound coaching advice.

## Lap 1 decision and handoff

Lap 1 review is complete. Preserve the locked test labels and results. Use development data for any later retrieval or excerpt improvements; do not tune against v1 or v2 held-out questions. Carry these fields into the Lap 2 API contract: question ID, support/abstention status, answer mode, report citation (source ID, page, evidence ID, excerpt), distinct recorded event evidence, provenance, limitations, and structured errors. Keep the excerpt relevance gap visible in product output and project claims until it is addressed on development data and evaluated on a newly frozen set.

## Checks performed

- `python3 scripts/validate_retrieval_benchmark_v2.py` — passed.
- SHA-256 verification of all five report PDFs against the locked manifest — passed.
- Citation excerpt, chunk, page, and provenance alignment — 30/30 passed.
- Raw StatsBomb window reconstruction — 12/12 windows and 132/132 selected event records matched.
- Not-covered abstention behavior — 2/2 passed.
- Same-match exclusion in historical retrieval — no same-match result in 12 top-100 result lists.
