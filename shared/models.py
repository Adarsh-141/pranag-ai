from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ── Intermediate pipeline models ──────────────────────────────────────────────

class ParsedPrompt(BaseModel):
    """Structured output produced by the LLM from a free-text user prompt."""
    crop: str
    location: str
    temperature: Optional[float] = None          # °C
    humidity: Optional[float] = None             # %
    rainfall: Optional[float] = None             # mm/year
    soil_type: Optional[str] = None
    stress_conditions: List[str] = Field(default_factory=list)
    target_traits: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)


class Trait(BaseModel):
    trait_name: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    domain: str = "biology"


class ResearchInsight(BaseModel):
    title: str
    key_finding: str
    relevance: float = Field(..., ge=0.0, le=1.0)
    source: str = "semantic_scholar"
    url: Optional[str] = None


# ── Final validated output ────────────────────────────────────────────────────

class Spec(BaseModel):
    """
    The canonical spec.json that is handed off to the simulation team (Srikar/Aryan).
    All fields are validated by Pydantic before the pipeline returns.
    """
    crop: str
    location: str
    temperature: float = 25.0
    humidity: Optional[float] = None
    rainfall: Optional[float] = None
    soil_type: Optional[str] = None
    stress_conditions: List[str] = Field(default_factory=list)
    target_traits: List[str] = Field(default_factory=list)
    retrieved_traits: List[str] = Field(default_factory=list)
    scientific_basis: List[str] = Field(default_factory=list)
    research_sources: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    pipeline_version: str = "1.0.0"
    generated_at: str = ""                               # ISO timestamp filled at build time
    research_titles: List[str] = Field(default_factory=list)  # paper titles (not just findings)
    research_years: List[Optional[int]] = Field(default_factory=list)  # paper years


# ── LangGraph state (must be a plain TypedDict for LangGraph) ─────────────────
# Defined in workflow.py to keep the graph self-contained.
