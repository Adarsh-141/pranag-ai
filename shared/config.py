from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── LLM (Ollama) ──────────────────────────────────────────────────────────
    # ollama_base_url: str = "http://localhost:11434"
    # ollama_model: str = "qwen2.5:3b"
    # ollama_timeout: int = 120          # seconds; R1 can be slow on first call
    # ── LLM (OpenRouter) ──────────────────────────────────────────────────────
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free" 
    llm_timeout: int = 30 # Reduced timeout since cloud is faster
    # ── Vector DB ─────────────────────────────────────────────────────────────
    chroma_collection: str = "entities"
    chroma_persist_dir: str = "./chroma_db"  # set "" for in-memory only

    # ── Pipeline ──────────────────────────────────────────────────────────────
    max_retries: int = 3
    search_top_k: int = 10

    # ── Research APIs ─────────────────────────────────────────────────────────
    semantic_scholar_base: str = "https://api.semanticscholar.org/graph/v1"
    semantic_scholar_api_key: Optional[str] = None   # optional; raises rate-limit without it
    research_results_limit: int = 5

    # ── Output ────────────────────────────────────────────────────────────────
    pipeline_version: str = "1.0.0"
    output_dir: str = "./outputs"                        # where spec.json files are saved
    srikar_endpoint: Optional[str] = None               # for now, there is no local endpoint available e.g. "http://srikar-sim:8000/spec"
    export_to_file: bool = True                          # set False to skip disk write
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
