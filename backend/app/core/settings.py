from __future__ import annotations

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field

from config.settings import VIVADO_PATH


backend_env = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(backend_env, override=False)
load_dotenv(find_dotenv(usecwd=True), override=False)


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Settings(BaseModel):
    app_name: str = "AI Hardware Design Copilot"
    environment: str = Field(default="development")
    vivado_path: str = Field(default_factory=lambda: os.getenv("VIVADO_PATH", VIVADO_PATH))
    vivado_part: str = Field(default_factory=lambda: os.getenv("VIVADO_PART", "xc7a35tcsg324-1"))
    rag_corpus_dir: str = Field(default_factory=lambda: os.getenv("RAG_CORPUS_DIR", r"backend\knowledge"))
    supabase_knowledge_table: str = Field(default_factory=lambda: os.getenv("SUPABASE_KNOWLEDGE_TABLE", "knowledge_chunks"))
    supabase_match_function: str = Field(default_factory=lambda: os.getenv("SUPABASE_MATCH_FUNCTION", "match_knowledge_chunks"))
    supabase_circuit_table: str = Field(default_factory=lambda: os.getenv("SUPABASE_CIRCUIT_TABLE", "generated_circuits"))
    rag_top_k: int = Field(default_factory=lambda: _get_int_env("RAG_TOP_K", 4))
    grok_api_key: str | None = Field(default_factory=lambda: os.getenv("GROK_API_KEY"))
    supabase_url: str | None = Field(default_factory=lambda: os.getenv("SUPABASE_URL"))
    supabase_key: str | None = Field(default_factory=lambda: os.getenv("SUPABASE_KEY"))
    default_technology_node: str = "65nm"


settings = Settings()
