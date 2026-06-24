"""
search_engine — Jay's data and search layer.

Jay's Task 6 — Integration Layer.
New file — did not exist in the GitHub repo.

Exposes the full public API so other modules can import cleanly:
    from search_engine import search_traits, populate, load_from_parquet
"""
from search_engine.similarity_search  import search_traits, search_traits_with_scores
from search_engine.vector_store       import (
    populate, load_from_parquet, get_stats, health_check,
)
from search_engine.embeddings         import embed, embed_batch, embed_cached
from search_engine.data_cleaner       import clean_parquet, clean_data
from search_engine.research_processor import (
    filter_research, extract_key_points, structure_summaries, process_research,
)

__all__ = [
    "search_traits", "search_traits_with_scores",
    "populate", "load_from_parquet", "get_stats", "health_check", "get_collection",
    "embed", "embed_batch", "embed_cached",
    "clean_parquet", "clean_data",
    "filter_research", "extract_key_points", "structure_summaries", "process_research",
]
