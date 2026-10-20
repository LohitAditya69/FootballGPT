"""Server-side LLM adapter for claim-level grounded coaching paraphrases."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from backend.api.answer_composer import (
    GroundedClaim,
    count_sentences as _count_answer_sentences,
    extract_grounded_claims,
    select_direct_passages,
)
from backend.api.config import Settings, settings
from backend.api.schemas import EventEvidence, HistoricalExample, TacticalPassage

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    text: str | None
    success: bool
    provider: str
    model: str
    error: str | None = None
    fallback_used: bool = False


SYSTEM_PROMPT = (
    "Rewrite only the supplied approved coaching claims as natural, concise advice. "
    "Preserve each claim's condition, direction, and uncertainty; do not add facts, tactics, "
    "players, events, or historical advice. Return strict JSON only in this shape: "
    '{"sentences":[{"claim_id":"C1","citation":"...","text":"one sentence"}]}. '
    "Use each approved claim at most once, include every approved claim, and put its exact "
    "approved citation in the matching sentence object. Do not put citations inside text."
)

_TOKEN_RE = re.compile(r"[a-z]+", re.I)
_CITATION_RE = re.compile(r"\(uefa-[a-z0-9-]+\s+p\.\d+\)", re.I)
_COMMON_WORDS = {
    "a", "about", "after", "an", "and", "as", "at", "ball", "be", "by", "for", "from",
    "if", "in", "into", "it", "of", "on", "or", "the", "their", "them", "they", "this",
    "to", "when", "where", "which", "while", "with", "you", "your", "we", "our", "team",
    "teams", "should", "can", "could", "may", "might", "will", "would", "try", "aim", "look",
    "seek", "focus", "prioritize", "prioritise", "option", "way", "once", "upon", "has", "have",
    "had", "is", "are", "was", "were", "become", "make", "makes", "made", "use", "uses", "using",
    "rather", "than", "then", "afterwards", "there", "here", "itself", "another", "one", "both", "each",
}
_OWN_HALF_WORDS = _COMMON_WORDS | {
    "own", "half", "regain", "regaining", "regained", "recover", "recovering", "recovered",
    "winning", "win", "wins", "ball", "possession", "forward", "early", "quick", "quickly",
    "promptly", "ahead", "advance", "advancing", "progress", "progressing", "move", "moves", "moving", "direct", "directly",
    "straight", "diagonal", "diagonally", "play", "plays", "playing", "pass", "passes", "passing", "first", "advanced",
    "player", "players", "attacker", "attackers", "teammate", "teammates", "space", "spaces",
    "behind", "beyond", "back", "line", "defensive", "defence", "defense", "towards", "toward",
    "through",
}
_MID_BLOCK_WORDS = _COMMON_WORDS | {
    "mid", "block", "regain", "regaining", "regained", "recover", "recovering", "recovered",
    "winning", "win", "ball", "possession", "keep", "keeping", "keeps", "kept", "protect",
    "protects", "protecting", "protected", "retain", "retaining", "retains", "retained", "secure",
    "secures", "securing", "secured", "maintain", "maintains", "maintaining", "maintained",
    "control", "controlling", "controlled", "priority", "midfield", "safe", "securely",
}


def _approved_claims(
    question: str,
    passages: list[TacticalPassage],
    fixed_chunks: dict[str, dict[str, Any]] | None,
) -> list[GroundedClaim]:
    selected = select_direct_passages(passages, question, fixed_chunks)
    return extract_grounded_claims(question, selected, fixed_chunks)


def build_evidence_prompt(
    question: str,
    passages: list[TacticalPassage],
    event_evidence: EventEvidence | None = None,
    historical_examples: list[HistoricalExample] | None = None,
    fixed_chunks: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Provide only the question and Lap 11's deterministic claim-to-citation set."""
    del event_evidence, historical_examples
    claims = _approved_claims(question, passages, fixed_chunks)
    payload = {
        "question": question,
        "approved_claims": [
            {"claim_id": f"C{index}", "claim": claim.text, "citation": claim.citation}
            for index, claim in enumerate(claims, start=1)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def count_sentences(text: str) -> int:
    return _count_answer_sentences(text)


def _claim_kind(claim: GroundedClaim) -> str | None:
    folded = claim.text.casefold()
    if "own half" in folded:
        return "own_half"
    if "mid-block" in folded:
        return "mid_block"
    return None


def _validate_claim_paraphrase(text: str, claim: GroundedClaim) -> tuple[bool, str]:
    cleaned = " ".join(text.split()).strip()
    if not cleaned or len(cleaned) > 420 or count_sentences(cleaned) != 1:
        return False, "Each claim must be one short sentence"
    if _CITATION_RE.search(cleaned) or "uefa-" in cleaned.casefold():
        return False, "Citation must be supplied separately from sentence text"
    if cleaned.casefold().rstrip(".!?") == claim.text.casefold().rstrip(".!?"):
        return False, "Output copied the approved claim instead of paraphrasing it"

    kind = _claim_kind(claim)
    tokens = set(_TOKEN_RE.findall(cleaned.casefold()))
    if kind == "own_half":
        if not re.search(r"\bown\s+(?:defensive\s+)?half\b", cleaned, re.I):
            return False, "Own-half condition was changed or omitted"
        claim_folded = claim.text.casefold()
        if "forward" in claim_folded and not re.search(r"\b(?:forward|ahead|advance|advancing|progress)\b", cleaned, re.I):
            return False, "Forward option was changed or omitted"
        if "early" in claim_folded and not re.search(r"\b(?:early|quick(?:ly)?|promptly)\b", cleaned, re.I):
            return False, "Early timing was changed or omitted"
        if not re.search(r"\b(?:pass|passing)\b", cleaned, re.I):
            return False, "Pass option was changed or omitted"
        if not re.search(r"\b(?:direct(?:ly)?|straight|diagonal(?:ly)?)\b", cleaned, re.I):
            return False, "Direct or diagonal route was changed or omitted"
        if not re.search(r"\b(?:advanced|advancing|player|teammate|space)\b", cleaned, re.I):
            return False, "Supported target or space was changed or omitted"
        allowed = set(_OWN_HALF_WORDS)
        if "early" not in claim_folded:
            allowed.difference_update({"early", "quick", "quickly", "promptly"})
        if "forward" not in claim_folded:
            allowed.difference_update({"forward", "ahead", "advance", "advancing", "progress", "progressing"})
    elif kind == "mid_block":
        if not re.search(r"\bmid[- ]block\b", cleaned, re.I):
            return False, "Mid-block condition was changed or omitted"
        if not re.search(r"\b(?:keep|keeping|retain|retaining|secure|securing|protect|protecting|maintain|maintaining)\b", cleaned, re.I):
            return False, "Possession-protection action was changed or omitted"
        if not re.search(r"\b(?:ball|possession)\b", cleaned, re.I):
            return False, "Ball or possession object was changed or omitted"
        allowed = _MID_BLOCK_WORDS
    else:
        return False, "No validator is available for this approved claim type"

    unsupported = sorted(tokens - allowed)
    if unsupported:
        return False, "Sentence contains details outside the approved claim"
    return True, "Valid paraphrase of approved claim"


def _validate_structured_output(
    generated_text: str,
    claims: list[GroundedClaim],
) -> tuple[bool, str, str | None]:
    try:
        payload = json.loads(generated_text)
    except (json.JSONDecodeError, TypeError):
        return False, "Generated output is not valid JSON", None
    if not isinstance(payload, dict) or set(payload) != {"sentences"}:
        return False, "Generated output has an unsupported structure", None
    rows = payload.get("sentences")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2:
        return False, "Generated output must contain one or two sentences", None
    if len(rows) != len(claims):
        return False, "Generated output must represent every approved claim exactly once", None

    claim_by_id = {f"C{index}": claim for index, claim in enumerate(claims, start=1)}
    rendered: list[str] = []
    used_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"claim_id", "citation", "text"}:
            return False, "Sentence entry has an unsupported structure", None
        claim_id = row.get("claim_id")
        if not isinstance(claim_id, str) or claim_id not in claim_by_id:
            return False, "Sentence refers to an unapproved claim", None
        if claim_id in used_ids:
            return False, "Approved claim was repeated", None
        claim = claim_by_id[claim_id]
        if row.get("citation") != claim.citation:
            return False, "Citation does not match the selected claim's source", None
        text = row.get("text")
        if not isinstance(text, str):
            return False, "Sentence text must be a string", None
        valid, reason = _validate_claim_paraphrase(text, claim)
        if not valid:
            return False, reason, None
        used_ids.add(claim_id)
        rendered.append(f"{' '.join(text.split()).rstrip('.!?')} ({claim.citation})")

    expected_ids = set(claim_by_id)
    if used_ids != expected_ids:
        return False, "Generated output omitted an approved claim", None
    answer = ". ".join(rendered) + "."
    if not 1 <= count_sentences(answer) <= 2:
        return False, "Rendered answer must contain one or two sentences", None
    return True, "Valid claim-grounded paraphrase", answer


def validate_llm_output(
    generated_text: str,
    passages: list[TacticalPassage],
    question: str | None = None,
    fixed_chunks: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    """Validate structured paraphrases against Lap 11's exact claim/citation mapping."""
    if not generated_text or len(generated_text) > 6000:
        return False, "Generated output is empty or exceeds the length bound"
    if not question:
        return False, "Question is required for claim-level validation"
    claims = _approved_claims(question, passages, fixed_chunks)
    if not claims:
        return False, "No approved claim is available for generation"
    valid, reason, _ = _validate_structured_output(generated_text, claims)
    return valid, reason


def _mock_paraphrase(claims: list[GroundedClaim]) -> str:
    rows = []
    for index, claim in enumerate(claims, start=1):
        if _claim_kind(claim) == "own_half":
            text = (
                "When you regain the ball in your own half, look to move forward early with a straight or "
                "diagonal pass toward an advanced teammate or into space behind the back line."
            )
        elif _claim_kind(claim) == "mid_block":
            text = "If you recover possession in a mid-block, focus on keeping the ball and protecting possession."
        else:
            text = claim.text
        rows.append({"claim_id": f"C{index}", "citation": claim.citation, "text": text})
    return json.dumps({"sentences": rows}, ensure_ascii=False)


class LLMClient:
    """Server-side provider adapter for evidence-constrained generation."""

    def __init__(self, cfg: Settings = settings) -> None:
        self.cfg = cfg
        self.provider = (cfg.llm_provider or "none").lower().strip()
        self.model = cfg.llm_model or "gpt-4o-mini"
        self.base_url = cfg.llm_base_url
        self.api_key = cfg.llm_api_key
        self.timeout = cfg.llm_timeout_seconds
        self.max_tokens = cfg.llm_max_tokens
        self.temperature = cfg.llm_temperature

    def is_configured(self) -> bool:
        if self.provider in ("none", "disabled", ""):
            return False
        if self.provider == "mock":
            return True
        if self.provider in ("openai", "openai_compatible"):
            return bool(self.api_key or self.base_url)
        if self.provider == "ollama":
            return True
        return bool(self.api_key)

    def generate_answer(
        self,
        question: str,
        passages: list[TacticalPassage],
        event_evidence: EventEvidence | None = None,
        historical_examples: list[HistoricalExample] | None = None,
        fixed_chunks: dict[str, dict[str, Any]] | None = None,
    ) -> LLMResult:
        if not passages:
            return LLMResult(None, False, self.provider, self.model, "No validated passages available", True)
        claims = _approved_claims(question, passages, fixed_chunks)
        if not claims:
            return LLMResult(None, False, self.provider, self.model, "No approved claims available", True)
        if not self.is_configured():
            return LLMResult(None, False, self.provider, self.model, "LLM provider is disabled", True)
        prompt = build_evidence_prompt(
            question, passages, event_evidence, historical_examples, fixed_chunks
        )
        try:
            if self.provider == "mock":
                raw_text = _mock_paraphrase(claims)
            elif self.provider in ("openai", "openai_compatible", "ollama", "gemini"):
                raw_text = self._generate_http_completion(prompt)
            else:
                return LLMResult(None, False, self.provider, self.model, "Unsupported provider", True)
            valid, validation_msg, answer = _validate_structured_output(raw_text, claims)
            if not valid or not answer:
                logger.warning("LLM output failed claim validation: %s", validation_msg)
                return LLMResult(None, False, self.provider, self.model, "Output validation failed", True)
            return LLMResult(answer, True, self.provider, self.model)
        except httpx.TimeoutException:
            logger.warning("LLM provider request timed out")
            return LLMResult(None, False, self.provider, self.model, "Provider request timed out", True)
        except httpx.HTTPStatusError as exc:
            message = "Provider rate limited" if exc.response.status_code == 429 else "Provider rejected the request"
            logger.warning("LLM provider returned HTTP status %s", exc.response.status_code)
            return LLMResult(None, False, self.provider, self.model, message, True)
        except httpx.ConnectError:
            logger.warning("LLM provider connection failed")
            return LLMResult(None, False, self.provider, self.model, "Provider connection failed", True)
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
            logger.warning("LLM provider returned malformed output")
            return LLMResult(None, False, self.provider, self.model, "Provider returned malformed output", True)
        except Exception as exc:
            logger.warning("LLM provider request failed with %s", type(exc).__name__)
            return LLMResult(None, False, self.provider, self.model, "Provider request failed", True)

    def _generate_http_completion(self, user_content: str) -> str:
        endpoint = self.base_url or "https://api.openai.com/v1"
        url = endpoint.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Provider message content is not text")
            return content
