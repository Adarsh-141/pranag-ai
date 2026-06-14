"""
Research Data Processor — Jay's Task 5

Filters, ranks, and structures research results from research_fetcher.py
before they reach spec_builder.py.

New file — did not exist in the GitHub repo.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MIN_RELEVANCE: float = 0.3
MAX_RESULTS:   int   = 5


def filter_research(insights: list[dict], min_relevance: float = MIN_RELEVANCE) -> list[dict]:
    """Remove low-relevance papers and sort by relevance descending."""
    filtered = [r for r in insights if r.get("relevance", 0) >= min_relevance]
    filtered.sort(key=lambda r: r.get("relevance", 0), reverse=True)
    dropped = len(insights) - len(filtered)
    if dropped:
        logger.info("[research_processor] Filtered %d low-relevance papers. Kept %d.", dropped, len(filtered))
    return filtered[:MAX_RESULTS]


def extract_key_points(insights: list[dict]) -> list[str]:
    """Extract deduplicated key findings for spec_builder.scientific_basis."""
    seen: set[str] = set()
    points: list[str] = []
    for r in insights:
        finding = r.get("key_finding", "").strip()
        if finding and finding not in seen:
            seen.add(finding)
            points.append(finding)
    return points


def structure_summaries(insights: list[dict]) -> list[dict]:
    """
    Guarantee every field exists and is the correct type.
    Prevents KeyError and type mismatch crashes in spec_builder.
    Also ensures the 'year' field is always present (fixes the bug
    where research_fetcher fetches 'year' from the API but never
    stores it in the insight dict).
    """
    structured = []
    for r in insights:
        structured.append({
            "title":       str(r.get("title",       "Untitled")),
            "key_finding": str(r.get("key_finding", "")),
            "relevance":   float(r.get("relevance", 0.0)),
            "source":      str(r.get("source",      "semantic_scholar")),
            "url":         str(r.get("url",         "")),
            "year":        r.get("year"),   # int or None
        })
    return structured


def process_research(insights: list[dict]) -> list[dict]:
    """
    Full pipeline: filter → structure → return.

    This is the single function workflow.py or research_fetcher.py
    should call before passing research results to spec_builder.

    Usage:
        from search_engine.research_processor import process_research
        clean = process_research(raw_insights)
    """
    filtered   = filter_research(insights)
    structured = structure_summaries(filtered)
    logger.info(
        "[research_processor] %d raw → %d structured summaries.",
        len(insights), len(structured),
    )
    return structured
