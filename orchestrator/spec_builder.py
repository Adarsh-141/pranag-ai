"""
Spec Builder

Combines parsed prompt + retrieved traits + research insights
→ raw dict for output_validator.py

Improvement over v1:
  • Confidence score rewards crop-specific trait matches
  • Warns when retrieved traits are mostly off-crop
"""
import logging
from datetime import datetime, timezone
from shared.config import settings

logger = logging.getLogger(__name__)


def build_spec(parsed: dict, traits: list[str], research: list[dict]) -> dict:
    crop = parsed.get("crop", "unknown")

    # ── Confidence heuristic ─────────────────────────────────────────────────
    missing_penalty = sum([
        0.10 if not parsed.get("temperature")                       else 0,
        0.10 if not parsed.get("location") or
                parsed["location"] == "unknown"                     else 0,
        0.05 if not parsed.get("stress_conditions")                 else 0,
        0.05 if crop == "unknown"                                   else 0,
    ])

    # Reward traits that mention the crop by name
    crop_trait_hits = sum(
        1 for t in traits if crop.lower() in t.lower()
    ) if crop != "unknown" else 0
    trait_bonus    = min(len(traits) * 0.02 + crop_trait_hits * 0.03, 0.15)
    research_bonus = min(len(research) * 0.02, 0.10)

    confidence = round(
        max(0.0, min(1.0, 0.80 - missing_penalty + trait_bonus + research_bonus)),
        2,
    )

    if crop != "unknown" and crop_trait_hits == 0 and len(traits) > 0:
        logger.warning(
            "[spec_builder] No crop-specific traits found for '%s'. "
            "Consider adding %s entries to vector_store.SEED_TRAITS.", crop, crop
        )

    return {
        "crop":              crop,
        "location":          parsed.get("location", "unknown"),
        "temperature":       parsed.get("temperature") or 25.0,
        "humidity":          parsed.get("humidity"),
        "rainfall":          parsed.get("rainfall"),
        "soil_type":         parsed.get("soil_type"),
        "stress_conditions": parsed.get("stress_conditions", []),
        "target_traits":     parsed.get("target_traits", []),
        "retrieved_traits":  traits,
        "scientific_basis":  [r["key_finding"] for r in research],
        "research_sources":  [r.get("url", "") for r in research],
        "research_titles":   [r.get("title", "") for r in research],        # NEW
        "research_years":    [r.get("year") for r in research],             # NEW
        "constraints":       parsed.get("constraints", {}),
        "confidence":        confidence,
        "pipeline_version":  settings.pipeline_version,
        "generated_at":      datetime.now(timezone.utc).isoformat(),        # NEW
    }
