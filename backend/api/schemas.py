"""Request and response schemas matching product API contract v1."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContextPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    match_id: str | None = Field(default=None, description="Optional StatsBomb match ID")
    trigger_event_id: str | None = Field(default=None, description="Optional StatsBomb event UUID")

    @field_validator("match_id", "trigger_event_id", mode="before")
    @classmethod
    def coerce_string(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., description="Tactical question (1-2000 characters)")
    context: ContextPayload | None = Field(default=None, description="Optional match/event grounding context")

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("question must be a string")
        trimmed = v.strip()
        if not (1 <= len(trimmed) <= 2000):
            raise ValueError("Question must contain 1–2000 characters.")
        return trimmed


class TacticalPassage(BaseModel):
    evidence_id: str
    source_id: str
    source_title: str
    page: int
    citation: str
    excerpt: str
    score: float


class EventEvidence(BaseModel):
    evidence_id: str
    match_id: str
    trigger_event_id: str
    trigger_event_type: str
    trigger_timestamp: str
    window_rule: str
    events: list[dict[str, Any]] = Field(default_factory=list)


class HistoricalExample(BaseModel):
    evidence_id: str
    case_id: str | int | None = None
    match_id: str
    team: str | None = None
    opponent: str | None = None
    timestamp: str | None = None
    event_type: str | None = None
    play_pattern: str | None = None
    location: list[float] | None = None
    formation: str | None = None
    historical_score: float
    similarity_breakdown: dict[str, float] = Field(default_factory=dict)
    source_split: str = "train"
    label: str = "similar recorded situation (train split, not UEFA coaching principle)"

    @field_validator("formation", mode="before")
    @classmethod
    def coerce_formation(cls, v: Any) -> str | None:
        if v is None:
            return None
        return str(v)


class ProvenanceTrace(BaseModel):
    schema_version: Literal["rgg-provenance-v1"] = "rgg-provenance-v1"
    question_id: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class AskResponse(BaseModel):
    schema_version: Literal["footballgpt-response-v1"] = "footballgpt-response-v1"
    request_id: str
    status: Literal["answered", "abstained"]
    support_status: Literal["conditional", "not_covered", "unknown"]
    answer_mode: Literal["extractive_evidence_brief", "abstain"]
    answer: str
    tactical_passages: list[TacticalPassage] = Field(default_factory=list)
    event_evidence: EventEvidence | None = None
    historical_examples: list[HistoricalExample] = Field(default_factory=list)
    provenance: ProvenanceTrace | None = None
    limitations: list[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    schema_version: Literal["footballgpt-error-v1"] = "footballgpt-error-v1"
    request_id: str
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = "1.0.0"
