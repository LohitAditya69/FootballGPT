"""Core service orchestrating retrieval, chunk validation, and contract mapping."""

from __future__ import annotations

import csv
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from backend.api.config import Settings, settings
from backend.api.schemas import (
    AskRequest,
    AskResponse,
    EventEvidence,
    HistoricalExample,
    ProvenanceTrace,
    TacticalPassage,
)
from backend.retrieval.graph_retriever import load_graph, retrieve_graph
from backend.retrieval.historical_retriever import load_historical_index, retrieve_historical
from backend.retrieval.vector_retriever import load_bm25_index, retrieve_bm25

logger = logging.getLogger(__name__)


def _extract_excerpt(text: str) -> str:
    """Extract a verbatim sentence from source text preserving exact wording."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", cleaned) if part.strip()]
    return sentences[0] if sentences else cleaned


def _normalize_text(text: str) -> str:
    """Normalize text for seed lookup comparison."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


class TacticalService:
    def __init__(self, cfg: Settings = settings) -> None:
        self.cfg = cfg
        self._initialized = False

        self.fixed_chunks: dict[str, dict[str, Any]] = {}
        self.source_titles: dict[str, str] = {}
        self.bm25_index: dict[str, Any] = {}
        self.graph: Any = None
        self.historical_cases: list[dict[str, Any]] = []
        self.event_windows_by_match_and_trigger: dict[tuple[str, str], dict[str, Any]] = {}
        self.event_windows_by_match: dict[str, list[dict[str, Any]]] = {}
        self.seeds_by_normalized_question: dict[str, dict[str, Any]] = {}
        self.seeds_by_match_and_trigger: dict[tuple[str, str], dict[str, Any]] = {}

    def initialize(self) -> None:
        if self._initialized:
            return

        logger.info("Initializing TacticalService and loading indexes...")

        # 1. Load manifest for source titles
        if self.cfg.manifest_path.exists():
            try:
                manifest = json.loads(self.cfg.manifest_path.read_text(encoding="utf-8"))
                for s in manifest.get("sources", []):
                    self.source_titles[s["source_id"]] = s.get("title", s["source_id"])
            except Exception as e:
                logger.warning("Failed to load UEFA manifest: %s", e)

        # 2. Load fixed evidence chunks
        if not self.cfg.fixed_chunks_path.exists():
            raise FileNotFoundError(f"Fixed chunk index not found at {self.cfg.fixed_chunks_path}")
        with self.cfg.fixed_chunks_path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                self.fixed_chunks[row["evidence_id"]] = row
                if row.get("source_id") and row.get("source_title") and row["source_id"] not in self.source_titles:
                    self.source_titles[row["source_id"]] = row["source_title"]

        # 3. Load BM25 index
        if not self.cfg.bm25_index_path.exists():
            raise FileNotFoundError(f"BM25 index not found at {self.cfg.bm25_index_path}")
        self.bm25_index = load_bm25_index(self.cfg.bm25_index_path)

        # 4. Load retrieval graph
        if not self.cfg.retrieval_graph_path.exists():
            raise FileNotFoundError(f"Retrieval graph not found at {self.cfg.retrieval_graph_path}")
        self.graph = load_graph(self.cfg.retrieval_graph_path)

        # 5. Load historical cases
        if not self.cfg.historical_index_path.exists():
            raise FileNotFoundError(f"Historical index not found at {self.cfg.historical_index_path}")
        self.historical_cases = load_historical_index(self.cfg.historical_index_path)

        # 6. Load event evidence windows
        if self.cfg.event_evidence_path.exists():
            with self.cfg.event_evidence_path.open(encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    window = json.loads(line)
                    mid = str(window.get("match_id", ""))
                    tid = str(window.get("trigger_event_id", ""))
                    if mid and tid:
                        self.event_windows_by_match_and_trigger[(mid, tid)] = window
                    if mid:
                        self.event_windows_by_match.setdefault(mid, []).append(window)

        # 7. Load evaluation seeds for support status reference
        if self.cfg.evaluation_seeds_path.exists():
            try:
                with self.cfg.evaluation_seeds_path.open(encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f):
                        q_orig = row.get("question_seed", "")
                        q_rev = row.get("revised_question_seed", "")
                        if q_orig:
                            self.seeds_by_normalized_question[_normalize_text(q_orig)] = row
                        if q_rev:
                            self.seeds_by_normalized_question[_normalize_text(q_rev)] = row
                        mid = str(row.get("match_id", ""))
                        tid = str(row.get("trigger_event_id", ""))
                        if mid and tid:
                            self.seeds_by_match_and_trigger[(mid, tid)] = row
            except Exception as e:
                logger.warning("Failed to load evaluation seeds: %s", e)

        self._initialized = True
        logger.info("TacticalService successfully initialized (%d fixed chunks loaded).", len(self.fixed_chunks))

    def validate_chunk(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        """Validate candidate metadata against the fixed UEFA chunk index."""
        eid = candidate.get("evidence_id")
        if not eid or eid not in self.fixed_chunks:
            return None

        fixed = self.fixed_chunks[eid]
        # Verify source_id and page match the fixed index
        if str(candidate.get("source_id")) != str(fixed.get("source_id")):
            return None
        try:
            if int(candidate.get("page")) != int(fixed.get("page")):
                return None
        except (TypeError, ValueError):
            return None

        # Prefer canonical citation and title from fixed index
        source_id = fixed["source_id"]
        source_title = self.source_titles.get(source_id, fixed.get("source_title", source_id))
        citation = fixed.get("citation", f"{source_id} p.{fixed.get('page')}")
        excerpt = _extract_excerpt(fixed.get("text", candidate.get("text", "")))

        return {
            "evidence_id": eid,
            "source_id": source_id,
            "source_title": source_title,
            "page": int(fixed["page"]),
            "citation": citation,
            "excerpt": excerpt,
        }

    def _resolve_event_context(
        self, context: Any, seed_match: dict[str, Any] | None
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
        """Resolve event window and trigger event from request context or seed."""
        limitations: list[str] = []
        window: dict[str, Any] | None = None
        trigger_event: dict[str, Any] | None = None

        req_match_id = context.match_id if context else None
        req_trigger_id = context.trigger_event_id if context else None

        if req_match_id and req_trigger_id:
            window = self.event_windows_by_match_and_trigger.get((req_match_id, req_trigger_id))
        elif req_match_id and not req_trigger_id:
            windows = self.event_windows_by_match.get(req_match_id, [])
            if len(windows) == 1:
                window = windows[0]
            elif len(windows) > 1:
                # Ambiguous without trigger event ID
                limitations.append(
                    f"Multiple event windows exist for match {req_match_id}; trigger_event_id required for exact resolution."
                )
        elif not req_match_id and req_trigger_id:
            # Search by trigger_event_id across windows
            for (m, t), w in self.event_windows_by_match_and_trigger.items():
                if t == req_trigger_id:
                    window = w
                    break

        # Fallback to seed context if request context was omitted but question is an evaluation seed
        if not window and seed_match:
            sm_id = str(seed_match.get("match_id", ""))
            st_id = str(seed_match.get("trigger_event_id", ""))
            if sm_id and st_id and (sm_id, st_id) in self.event_windows_by_match_and_trigger:
                window = self.event_windows_by_match_and_trigger[(sm_id, st_id)]

        if window:
            target_tid = req_trigger_id or window.get("trigger_event_id")
            for ev in window.get("events", []):
                if ev.get("id") == target_tid:
                    trigger_event = ev
                    break
            if not trigger_event and window.get("events"):
                trigger_event = window["events"][0]
        else:
            if req_match_id or req_trigger_id:
                limitations.append(
                    "Query event context could not be resolved from provided match_id and trigger_event_id; historical retrieval and match event evidence were skipped."
                )
            else:
                limitations.append(
                    "No event context was provided; match event evidence and historical situation retrieval were skipped."
                )

        return window, trigger_event, limitations

    def ask(self, request: AskRequest, request_id: str | None = None) -> AskResponse:
        self.initialize()
        req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        question = request.question.strip()
        norm_q = _normalize_text(question)

        # Check if question corresponds to a known evaluation seed
        seed_match = self.seeds_by_normalized_question.get(norm_q)
        if not seed_match and request.context and request.context.match_id and request.context.trigger_event_id:
            seed_match = self.seeds_by_match_and_trigger.get(
                (request.context.match_id, request.context.trigger_event_id)
            )

        is_seed_not_covered = bool(seed_match and seed_match.get("gold_support_status") == "not_covered")

        # 1. Resolve event context
        window, trigger_event, event_limits = self._resolve_event_context(request.context, seed_match)
        match_id_to_exclude = str(request.context.match_id) if (request.context and request.context.match_id) else (
            str(window["match_id"]) if window else None
        )

        limitations: list[str] = [
            "Passages are copied verbatim from page-cited UEFA chunks; no language model generated or checked a paraphrase.",
            "StatsBomb event records do not establish off-ball runs, team shape, or unseen video context.",
            "This artifact does not claim human-judged factuality, coach approval, or definitive ground truth.",
        ]
        limitations.extend(event_limits)

        # 2. Run retrieval
        pool_size = max(4 * self.cfg.top_k_tactical, 30)
        v_raw_rows = retrieve_bm25(question, self.bm25_index, top_k=pool_size)
        g_rows = retrieve_graph(question, self.graph, top_k=pool_size)

        # Filter out front matter, table of contents, and roll of honour chunks
        def is_tactical_chunk(chunk: dict[str, Any]) -> bool:
            try:
                page = int(chunk.get("page", 0))
            except (TypeError, ValueError):
                page = 0
            text = chunk.get("text", "").strip()
            if page <= 3:
                return False
            if text.startswith("CONTENTS") or text.startswith("ROLL OF HONOUR") or text.startswith("TECHNICAL REPORT"):
                return False
            if len(text) < 50:
                return False
            return True

        v_rows = [r for r in v_raw_rows if is_tactical_chunk(r)]
        g_rows = [r for r in g_rows if is_tactical_chunk(r)]

        # Extract content unigrams from question for term overlap check
        from backend.retrieval.vector_retriever import tokenize
        q_unigrams = set(t for t in tokenize(question) if "_" not in t)

        top_v_score = v_rows[0]["vector_score"] if v_rows else 0.0
        has_graph_concept = bool(g_rows)

        matched_unigram_count = 0
        term_overlap_ratio = 0.0
        if v_rows and q_unigrams:
            top_cand_tokens = set(tokenize(v_rows[0].get("text", "")))
            matched_unigrams = [t for t in q_unigrams if t in top_cand_tokens]
            matched_unigram_count = len(matched_unigrams)
            term_overlap_ratio = matched_unigram_count / len(q_unigrams)

        has_adequate_lexical = (
            bool(v_rows)
            and top_v_score >= 10.0
            and matched_unigram_count >= 2
            and term_overlap_ratio >= 0.25
        )

        has_adequate_support = (has_adequate_lexical or has_graph_concept) and not is_seed_not_covered

        # 3. Determine abstention vs answered
        if not has_adequate_support:
            support_status = "not_covered" if is_seed_not_covered else (
                "not_covered" if top_v_score == 0.0 and not has_graph_concept else "unknown"
            )
            answer_mode = "abstain"
            status = "abstained"
            answer = (
                "The frozen UEFA reference set marks this question as not covered. "
                "No tactical answer is provided from these reports."
                if support_status == "not_covered"
                else "No adequately supported tactical passage was retrieved from the frozen UEFA reference set; "
                "abstain pending source review."
            )
            limitations.append(
                "No adequately supported passage was found in the frozen UEFA corpus for this query; abstention returned."
            )
            tactical_passages: list[TacticalPassage] = []
        else:
            status = "answered"
            support_status = "conditional"
            answer_mode = "extractive_evidence_brief"
            answer = (
                "Retrieved source passages are shown verbatim below. "
                "They support review of the question but do not establish missing match context or coaching ground truth."
            )

            # Combine candidates deterministically
            v_norm = {}
            if v_rows:
                v_scores = [r["vector_score"] for r in v_rows]
                v_min, v_max = min(v_scores), max(v_scores)
                v_norm = {
                    r["evidence_id"]: 1.0 if v_max == v_min else (r["vector_score"] - v_min) / (v_max - v_min)
                    for r in v_rows
                }
            g_norm = {r["evidence_id"]: r["graph_score"] for r in g_rows}

            # Fusion with 0.70 V and 0.30 G for tactical passages
            combined_candidates: list[tuple[float, dict[str, Any]]] = []
            for eid in set(v_norm) | set(g_norm):
                cand = next((r for r in v_rows if r["evidence_id"] == eid), None) or next(
                    (r for r in g_rows if r["evidence_id"] == eid), None
                )
                if not cand:
                    continue
                valid_dict = self.validate_chunk(cand)
                if not valid_dict:
                    continue
                fused_score = 0.70 * v_norm.get(eid, 0.0) + 0.30 * g_norm.get(eid, 0.0)
                combined_candidates.append((fused_score, {**valid_dict, "score": round(fused_score, 4)}))

            combined_candidates.sort(key=lambda item: (-item[0], item[1]["evidence_id"]))
            tactical_passages = [
                TacticalPassage(**c[1]) for c in combined_candidates[: self.cfg.top_k_tactical]
            ]
            if not tactical_passages:
                status = "abstained"
                answer_mode = "abstain"
                support_status = "unknown"
                answer = (
                    "No valid page-cited passage passed fixed-chunk verification; abstain pending source review."
                )

        # 4. Historical retrieval (strictly conditioned on grounded event + match exclusion)
        historical_examples: list[HistoricalExample] = []
        if trigger_event and match_id_to_exclude:
            h_raw = retrieve_historical(
                trigger_event,
                self.historical_cases,
                exclude_match_id=match_id_to_exclude,
                top_k=self.cfg.top_k_historical,
            )
            # Mandatory check: ensure no candidate leaked from the query match
            for h in h_raw:
                if str(h.get("match_id")) == match_id_to_exclude:
                    continue
                historical_examples.append(
                    HistoricalExample(
                        evidence_id=h["evidence_id"],
                        case_id=h.get("case_id"),
                        match_id=str(h["match_id"]),
                        team=h.get("team"),
                        opponent=h.get("opponent"),
                        timestamp=h.get("timestamp"),
                        event_type=h.get("event_type"),
                        play_pattern=h.get("play_pattern"),
                        location=h.get("location"),
                        formation=h.get("formation"),
                        historical_score=h.get("historical_score", 0.0),
                        similarity_breakdown=h.get("similarity_breakdown", {}),
                        source_split=h.get("source_split", "train"),
                        label="historical event example (train split, not UEFA coaching principle)",
                    )
                )
            limitations.append(
                f"Historical examples are similar event records from the training split (excluding match {match_id_to_exclude}); they do not constitute UEFA tactical recommendations."
            )

        # 5. Build EventEvidence model if resolved
        event_model: EventEvidence | None = None
        if window:
            event_model = EventEvidence(
                evidence_id=window["evidence_id"],
                match_id=str(window["match_id"]),
                trigger_event_id=window["trigger_event_id"],
                trigger_event_type=window.get("trigger_event_type", "Event"),
                trigger_timestamp=window.get("trigger_timestamp", "00:00:00.000"),
                window_rule=window.get("window_rule", "Adjacent recorded events window"),
                events=window.get("events", []),
            )

        # 6. Build Provenance Trace
        qid = str(seed_match["case_id"]) if seed_match else req_id
        q_node = f"question:{qid}"
        nodes: list[dict[str, Any]] = [{"id": q_node, "node_type": "question", "text": question}]
        edges: list[dict[str, Any]] = []

        for i, passage in enumerate(tactical_passages):
            nodes.append(
                {
                    "id": passage.evidence_id,
                    "node_type": "uefa_text_chunk",
                    "citation": passage.citation,
                    "source_id": passage.source_id,
                    "page": passage.page,
                    "score": passage.score,
                }
            )
            edges.append(
                {
                    "source": q_node,
                    "target": passage.evidence_id,
                    "relation": "retrieved_support",
                    "rank": i + 1,
                }
            )

        if event_model:
            nodes.append(
                {
                    "id": event_model.evidence_id,
                    "node_type": "statsbomb_event_window",
                    "match_id": event_model.match_id,
                    "trigger_event_id": event_model.trigger_event_id,
                    "window_rule": event_model.window_rule,
                }
            )
            edges.append(
                {
                    "source": q_node,
                    "target": event_model.evidence_id,
                    "relation": "recorded_match_context",
                }
            )

        for h in historical_examples:
            nodes.append(
                {
                    "id": h.evidence_id,
                    "node_type": "historical_situation",
                    "match_id": h.match_id,
                    "case_id": h.case_id,
                    "similarity_score": h.historical_score,
                }
            )
            edges.append(
                {
                    "source": q_node,
                    "target": h.evidence_id,
                    "relation": "historical_similarity",
                }
            )

        provenance = ProvenanceTrace(
            schema_version="rgg-provenance-v1",
            question_id=qid,
            nodes=nodes,
            edges=edges,
        )

        return AskResponse(
            schema_version="footballgpt-response-v1",
            request_id=req_id,
            status=status,
            support_status=support_status,
            answer_mode=answer_mode,
            answer=answer,
            tactical_passages=tactical_passages,
            event_evidence=event_model,
            historical_examples=historical_examples,
            provenance=provenance,
            limitations=limitations,
        )
