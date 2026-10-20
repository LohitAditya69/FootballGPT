"""Configuration settings for FootballGPT Backend API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = project_root / "backend" / "data"
    reports_dir: Path = project_root / "reports"

    # Evidence and index files
    fixed_chunks_path: Path = data_dir / "uefa_evidence_chunks.jsonl"
    manifest_path: Path = reports_dir / "uefa_report_manifest.json"
    bm25_index_path: Path = data_dir / "uefa_bm25_index.json"
    retrieval_graph_path: Path = data_dir / "retrieval_graph.json"
    historical_index_path: Path = data_dir / "historical_train_sample.jsonl.gz"
    event_evidence_path: Path = data_dir / "question_event_evidence.jsonl"
    ranking_config_path: Path = project_root / "backend" / "retrieval" / "ranking_config.json"

    # Retrieval and evidence quality thresholds
    min_bm25_score_threshold: float = 4.0
    min_graph_score_threshold: float = 0.5
    top_k_tactical: int = 3
    top_k_historical: int = 3

    # Server settings
    host: str = os.getenv("FOOTBALLGPT_HOST", "127.0.0.1")
    port: int = int(os.getenv("FOOTBALLGPT_PORT", "8000"))

    # Server-side LLM provider configuration (outside source control)
    llm_provider: str = os.getenv("FOOTBALLGPT_LLM_PROVIDER", "none")
    llm_model: str = os.getenv("FOOTBALLGPT_LLM_MODEL", "gpt-4o-mini")
    llm_base_url: str | None = os.getenv("FOOTBALLGPT_LLM_BASE_URL", None)
    llm_api_key: str | None = os.getenv("FOOTBALLGPT_LLM_API_KEY", None)
    llm_timeout_seconds: float = float(os.getenv("FOOTBALLGPT_LLM_TIMEOUT", "8.0"))
    llm_max_tokens: int = int(os.getenv("FOOTBALLGPT_LLM_MAX_TOKENS", "300"))
    llm_temperature: float = float(os.getenv("FOOTBALLGPT_LLM_TEMPERATURE", "0.2"))


settings = Settings()
