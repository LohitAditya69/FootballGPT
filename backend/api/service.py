"""Core service orchestrating retrieval, chunk validation, and contract mapping."""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from backend.api.answer_composer import (
    GENERIC_ABSTENTION_NOTICE,
    _source_sentences,
    compose_grounded_answer,
    is_clean_tactical_sentence,
    select_direct_passages,
)
from backend.api.config import Settings, settings
from backend.api.llm_client import LLMClient
from backend.api.schemas import (
    AskRequest,
    AskResponse,
    EventEvidence,
    HistoricalExample,
    ProvenanceTrace,
    TacticalPassage,
)
from backend.retrieval.combined_retriever import load_ranking_config, normalize_channel
from backend.retrieval.graph_retriever import load_graph, retrieve_graph
from backend.retrieval.historical_retriever import (
    load_historical_index,
    parse_question_to_event_query,
    retrieve_historical,
)
from backend.retrieval.vector_retriever import load_bm25_index, retrieve_bm25

logger = logging.getLogger(__name__)


def _extract_excerpt(text: str, query: str | None = None) -> str:
    """Return up to three query-matched source sentences, excluding headings."""
    sentences = [sentence for sentence in _source_sentences(text) if is_clean_tactical_sentence(sentence)]
    if not sentences:
        return text.strip()
    if query:
        from backend.api.answer_composer import _normalized_terms

        query_terms = _normalized_terms(query)
        if query_terms:
            scored = [
                (len(query_terms & _normalized_terms(sentence)), index, sentence)
                for index, sentence in enumerate(sentences)
            ]
            matched = [item for item in scored if item[0] > 0]
            if matched:
                chosen = sorted(sorted(matched, key=lambda item: (-item[0], item[1]))[:3], key=lambda item: item[1])
                return "\n".join(sentence for _, _, sentence in chosen)
    return sentences[0]


class TacticalService:
    def __init__(self, cfg: Settings = settings) -> None:
        self.cfg = cfg
        self._initialized = False

        self.fixed_chunks: dict[str, dict[str, Any]] = {}
        self.source_titles: dict[str, str] = {}
        self.bm25_index: dict[str, Any] = {}
        self.graph: Any = None
        self.historical_cases: list[dict[str, Any]] = []
        self.ranking_config: dict[str, Any] = {}
        self.tactical_weights: dict[str, float] = {}
        self.event_windows_by_match_and_trigger: dict[tuple[str, str], dict[str, Any]] = {}
        self.event_windows_by_match: dict[str, list[dict[str, Any]]] = {}
        self.llm_client = LLMClient(cfg)

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

        # Keep live API scoring aligned with the configuration used by the
        # retrieval evaluation scripts.
        self.ranking_config = load_ranking_config(self.cfg.ranking_config_path)
        bm25_cfg = self.ranking_config.get("bm25", {})
        if (
            float(self.bm25_index.get("k1", -1)) != float(bm25_cfg.get("k1", -2))
            or float(self.bm25_index.get("b", -1)) != float(bm25_cfg.get("b", -2))
        ):
            raise ValueError("BM25 index parameters do not match ranking_config.json")
        configured_weights = self.ranking_config["weights"]
        tactical_total = float(configured_weights["alpha"]) + float(configured_weights["beta"])
        if tactical_total <= 0:
            raise ValueError("Tactical BM25/graph weights must sum to a positive value")
        self.tactical_weights = {
            "V": float(configured_weights["alpha"]) / tactical_total,
            "G": float(configured_weights["beta"]) / tactical_total,
        }

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

        self._initialized = True
        logger.info("TacticalService successfully initialized (%d fixed chunks loaded).", len(self.fixed_chunks))

    def validate_chunk(self, candidate: dict[str, Any], query: str | None = None) -> dict[str, Any] | None:
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
        excerpt = _extract_excerpt(fixed.get("text", candidate.get("text", "")), query)

        return {
            "evidence_id": eid,
            "source_id": source_id,
            "source_title": source_title,
            "page": int(fixed["page"]),
            "citation": citation,
            "excerpt": excerpt,
        }

    def _resolve_event_context(
        self, context: Any
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
        """Resolve an event window only from explicit request context."""
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
                    "No exact match event context was provided; exact match event evidence was skipped."
                )

        return window, trigger_event, limitations

    def ask(self, request: AskRequest, request_id: str | None = None) -> AskResponse:
        self.initialize()
        req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        question = request.question.strip()
        # 1. Resolve event context
        window, trigger_event, event_limits = self._resolve_event_context(request.context)
        unresolved_event_context = (
            (request.context is not None and (request.context.match_id or request.context.trigger_event_id) and not window)
            or (window is None and any(kw in question.lower() for kw in ["match", "pass from", "recorded after", "intercepted", "restart"]))
        )
        match_id_to_exclude = str(request.context.match_id) if (request.context and request.context.match_id) else (
            str(window["match_id"]) if window else None
        )

        limitations: list[str] = [
            "Returned passages are copied verbatim from page-cited UEFA chunks; deterministic coaching claims map to their supporting returned source sentences.",
            "StatsBomb event records do not establish off-ball runs, team shape, or unseen video context.",
            "This artifact does not claim human-judged factuality, coach approval, or definitive ground truth.",
        ]
        limitations.extend(event_limits)

        # 2. Run retrieval
        pool_size = max(4 * self.cfg.top_k_tactical, 20)
        v_raw_rows = retrieve_bm25(question, self.bm25_index, top_k=pool_size)
        g_rows = retrieve_graph(question, self.graph, top_k=pool_size)

        # Filter out front matter, table of contents, drill sessions, and match goal recaps
        def is_tactical_chunk(chunk: dict[str, Any]) -> bool:
            try:
                page = int(chunk.get("page", 0))
            except (TypeError, ValueError):
                page = 0
            text = chunk.get("text", "").strip()
            if page <= 3:
                return False
            if len(text) < 50:
                return False
            if re.search(r"^(?:CONTENTS|ROLL OF HONOUR|TECHNICAL REPORT)", text, re.I):
                return False
            # Exclude training session drill cards, equipment/player counts, and pitch markings
            if re.search(
                r"session organisation|coaching points\s*[•]|\b\d+\s*players\s*\+\s*\d+\s*goalkeepers"
                r"|purple team|oranges must|\bdrill\b",
                text,
                re.I,
            ):
                return False
            # Exclude chronological tournament goal-scoring match recaps
            if re.search(r"how the goal was scored", text, re.I):
                return False
            return True

        v_rows = [r for r in v_raw_rows if is_tactical_chunk(r)]
        g_rows = [r for r in g_rows if is_tactical_chunk(r)]

        # 3. Retrieve and validate candidate evidence before deciding whether to abstain.
        # A lexical top-hit threshold can hide a directly relevant passage ranked
        # below a keyword-heavy result, so answer support is decided by the
        # sentence-level topic/role/action check over the wider candidate pool.
        status = "answered"
        support_status = "conditional"
        answer_mode = "extractive_evidence_brief"
        answer = ""

        v_norm = normalize_channel(v_rows, "vector_score")
        g_norm = normalize_channel(g_rows, "graph_score")
        combined_candidates: list[tuple[float, dict[str, Any]]] = []
        for eid in set(v_norm) | set(g_norm):
            cand = next((r for r in v_rows if r["evidence_id"] == eid), None) or next(
                (r for r in g_rows if r["evidence_id"] == eid), None
            )
            if not cand:
                continue
            valid_dict = self.validate_chunk(cand, question)
            if not valid_dict:
                continue
            fused_score = (
                self.tactical_weights["V"] * v_norm.get(eid, 0.0)
                + self.tactical_weights["G"] * g_norm.get(eid, 0.0)
            )
            combined_candidates.append((fused_score, {**valid_dict, "score": round(fused_score, 4)}))

        combined_candidates.sort(key=lambda item: (-item[0], item[1]["evidence_id"]))
        candidate_passages = [
            TacticalPassage(**candidate)
            for _, candidate in combined_candidates[:pool_size]
        ]
        tactical_passages = select_direct_passages(
            candidate_passages, question, self.fixed_chunks
        )
        if not tactical_passages:
            status = "abstained"
            answer_mode = "abstain"
            support_status = "unknown"
            answer = GENERIC_ABSTENTION_NOTICE
            limitations.append(
                "The ranked candidate pool contained no clean sentence with a specific topic, role, and action match; abstention returned."
            )

        # 4. Historical retrieval (strictly conditioned on grounded event + match exclusion OR question-derived search)
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
                        label="similar recorded situation (train split, not UEFA coaching principle)",
                    )
                )
            limitations.append(
                f"Historical examples are similar event records from the training split (excluding match {match_id_to_exclude}); they do not constitute UEFA tactical recommendations."
            )
            if historical_examples:
                limitations.append(
                    "Historical scores are fixed-weight agreement on comparable recorded metadata; incomplete feature coverage is shown in similarity_breakdown. Scores are not probabilities or judgments of tactical similarity or effectiveness."
                )
        elif not (request.context and (request.context.match_id or request.context.trigger_event_id)):
            # Question-only request: derive bounded event features directly from question text
            query_event_features, unrep_reason = parse_question_to_event_query(question)
            if query_event_features:
                if unrep_reason:
                    limitations.append(unrep_reason)
                h_raw = retrieve_historical(
                    query_event_features,
                    self.historical_cases,
                    exclude_match_id=None,
                    top_k=self.cfg.top_k_historical,
                    min_score_threshold=0.40,
                )
                for h in h_raw:
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
                            label="similar recorded situation (train split, not UEFA coaching principle)",
                        )
                    )
                if historical_examples:
                    limitations.append(
                        "Historical examples are similar recorded event situations from the StatsBomb training split; "
                        "they illustrate recorded patterns but do not constitute UEFA tactical principles or proof of effectiveness."
                    )
                    limitations.append(
                        "Historical scores are fixed-weight agreement on comparable recorded metadata; incomplete feature coverage is shown in similarity_breakdown. Scores are not probabilities or judgments of tactical similarity or effectiveness."
                    )
                else:
                    limitations.append(
                        "No training-split match situations met the similarity threshold for the question's event features."
                    )
                if query_event_features.get("event_type_scope") == "regain_proxy":
                    limitations.append(
                        "Generic ball-winning language is matched only to recorded Interception anchors in the available sampled index; it is a narrow event-type proxy, not an exhaustive set of regains. The train candidate index stores anchor records only, so no ordered post-event sequence is available to show."
                    )
            else:
                if unrep_reason:
                    limitations.append(unrep_reason)
                else:
                    limitations.append(
                        "No event context was provided and question does not correspond to discrete recorded on-ball events; "
                        "match situation retrieval was skipped."
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

        # 6. Paraphrase only claim types with an explicit validator; every failure
        # returns to the deterministic evidence composer.
        if status == "answered" and tactical_passages:
            answer = None
            provider_configured = False
            try:
                provider_configured = self.llm_client.is_configured()
            except Exception as exc:
                logger.warning("LLM provider configuration check failed with %s", type(exc).__name__)

            if provider_configured:
                try:
                    llm_result = self.llm_client.generate_answer(
                        question=question,
                        passages=tactical_passages,
                        event_evidence=event_model,
                        historical_examples=historical_examples,
                        fixed_chunks=self.fixed_chunks,
                    )
                except Exception as exc:
                    logger.warning("LLM generation failed with %s; using deterministic fallback", type(exc).__name__)
                    llm_result = None

                if llm_result is not None and llm_result.success and llm_result.text:
                    answer = llm_result.text
                    limitations.append(
                        "Coaching wording was paraphrased by the configured server-side LLM; each sentence was checked against an approved Lap 11 claim and its returned citation."
                    )
                else:
                    limitations.append(
                        "LLM paraphrase was unavailable or failed claim validation; the deterministic Lap 11 answer was used."
                    )

            if answer is None:
                answer = compose_grounded_answer(
                    question=question,
                    tactical_passages=tactical_passages,
                    event_evidence=event_model,
                    historical_examples=historical_examples,
                    unresolved_event_context=unresolved_event_context,
                    fixed_chunks=self.fixed_chunks,
                )
            if answer == GENERIC_ABSTENTION_NOTICE:
                status = "abstained"
                support_status = "unknown"
                answer_mode = "abstain"
                tactical_passages = []
                limitations.append("No directly responsive source claim was available; abstention returned.")

        # 7. Build Provenance Trace
        qid = req_id
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
