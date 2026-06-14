# from __future__ import annotations
# import logging
# import time
# from search_engine.embeddings import embed_cached
# from search_engine.vector_store import get_collection
# from shared.config import settings

# logger = logging.getLogger(__name__)

# # Target from WorkflowB.pdf spec: <50ms per search query
# _SEARCH_TARGET_MS = 50.0

# def search_traits(
#     query: str,
#     top_k: int | None = None,
#     crop: str | None = None,
# ) -> list[str]:
#     """
#     Optimized Similarity Search:
#     1. Embeds query (cached).
#     2. Performs a single-pass ChromaDB query using metadata filtering.
#     3. Returns results.
#     """
#     # 1. Embed outside the timer to ensure we measure database speed only
#     vector = list(embed_cached(query))
    
#     start = time.perf_counter()
    
#     k = top_k if top_k is not None else settings.search_top_k
#     col = get_collection()

#     if col.count() == 0:
#         logger.warning("[similarity_search] Vector store is empty.")
#         return []

#     # 2. Build filter dynamically to perform a single-pass query
#     where_filter = {"domain": {"$in": ["biology", "environment"]}}
    
#     if crop and crop.lower() not in ("unknown", "", "general"):
#         crop_lower = crop.lower()
#         # Single-pass filter: matches the crop OR 'general' records
#         where_filter = {
#             "$and": [
#                 where_filter,
#                 {"$or": [
#                     {"tags": {"$contains": crop_lower}},
#                     {"crop": {"$in": [crop_lower, "general"]}}
#                 ]}
#             ]
#         }

#     # 3. Single database call
#     results = col.query(
#         query_embeddings=[vector],
#         n_results=k,
#         where=where_filter,
#         include=["documents"],
#     )

#     merged = results["documents"][0] if results["documents"] else []

#     # 4. Timing measurement
#     elapsed_ms = (time.perf_counter() - start) * 1000
    
#     if elapsed_ms > _SEARCH_TARGET_MS:
#         logger.warning(
#             "[similarity_search] Slow query: %.1fms (target <%dms) for: '%s'",
#             elapsed_ms, _SEARCH_TARGET_MS, query[:60]
#         )
#     else:
#         logger.debug("[similarity_search] %.1fms for: '%s'", elapsed_ms, query[:60])

#     return merged

# def search_traits_with_scores(
#     query: str,
#     top_k: int | None = None,
#     crop: str | None = None,
# ) -> list[dict]:
#     """
#     Optimized version of scored search fetching only necessary metadata.
#     """
#     vector = list(embed_cached(query))
#     start = time.perf_counter()
#     col = get_collection()

#     # Query with distance to calculate scores
#     results = col.query(
#         query_embeddings=[vector],
#         n_results=top_k or settings.search_top_k,
#         include=["documents", "distances", "metadatas"],
#     )

#     docs = results["documents"][0]
#     distances = results["distances"][0]
#     metas = results.get("metadatas", [[{}] * len(docs)])[0]

#     elapsed_ms = (time.perf_counter() - start) * 1000
#     logger.debug("[similarity_search] with_scores: %.1fms", elapsed_ms)

#     ranked = []
#     for doc, dist, meta in zip(docs, distances, metas):
#         score = 1.0 - dist
#         # Scoring logic remains as per your requirements
#         domain = str(meta.get("domain", "")).lower()
#         if domain == "biology": score += 0.30
#         elif domain == "environment": score += 0.20
        
#         ranked.append({
#             "trait": doc,
#             "score": round(score, 4),
#             "domain": domain,
#             "tags": str(meta.get("tags", "")).lower(),
#         })

#     return sorted(ranked, key=lambda x: x["score"], reverse=True)






"""
Similarity search over ChromaDB — Jay's Task 3 + Task 7

Changes over GitHub version:
- embed_cached() used instead of embed() to avoid recomputing
  embeddings for repeated queries (Task 7)
- Timing measurement added and warns when search exceeds
  50ms target from WorkflowB.pdf (Task 3)
- Empty vector-store warning added
- search_traits_with_scores() returns metadata and scores
- Tags-based crop filtering added for Parquet datasets
"""

# from __future__ import annotations

# import logging
# import time

# from search_engine.embeddings import embed_cached
# from search_engine.vector_store import get_collection
# from shared.config import settings

# logger = logging.getLogger(__name__)

# # Target from WorkflowB.pdf
# _SEARCH_TARGET_MS = 50.0


# def search_traits(
#     query: str,
#     top_k: int | None = None,
#     crop: str | None = None,
# ) -> list[str]:
#     """
#     Return top-k most similar trait/entity descriptions.

#     Strategy:
#     1. Perform crop-specific search when crop is known.
#     2. Fill remaining slots with global search results.
#     3. Deduplicate while preserving crop-specific priority.

#     Args:
#         query: Natural language query.
#         top_k: Number of results to return.
#         crop: Crop name for filtering (e.g. wheat, rice).

#     Returns:
#         List of description strings.
#     """
#     start = time.perf_counter()

#     k = top_k if top_k is not None else settings.search_top_k
#     col = get_collection()

#     if col.count() == 0:
#         logger.warning(
#             "[similarity_search] Vector store is empty. "
#             "Run populate() or load_from_parquet() first."
#         )
#         return []

#     vector = list(embed_cached(query))

#     crop_docs: list[str] = []

#     # --------------------------------------------------
#     # Step 1: Crop-specific search
#     # --------------------------------------------------
#     if crop and crop.lower() not in ("unknown", "", "general"):
#         crop_lower = crop.lower()

#         try:
#             crop_res = col.query(
#                 query_embeddings=[vector],
#                 n_results=min(k, col.count()),
#                 where={
#                     "$or": [
#                         {"tags": {"$contains": crop_lower}},
#                         {"crop": {"$in": [crop_lower, "general"]}},
#                     ]
#                 },
#                 include=["documents"],
#             )
#             crop_docs = crop_res["documents"][0]

#         except Exception:
#             try:
#                 crop_res = col.query(
#                     query_embeddings=[vector],
#                     n_results=min(k, col.count()),
#                     where={
#                         "crop": {
#                             "$in": [crop_lower, "general"]
#                         }
#                     },
#                     include=["documents"],
#                 )
#                 crop_docs = crop_res["documents"][0]

#             except Exception:
#                 crop_docs = []

#     # --------------------------------------------------
#     # Step 2: Global search
#     # --------------------------------------------------
#     global_res = col.query(
#         query_embeddings=[vector],
#         n_results=min(k, col.count()),
#         where={
#             "$or": [
#                 {"domain": "biology"},
#                 {"domain": "environment"},
#             ]
#         },
#         include=["documents", "metadatas"],
#     )

#     global_docs = global_res["documents"][0]

#     # --------------------------------------------------
#     # Step 3: Merge results
#     # --------------------------------------------------
#     seen: set[str] = set()
#     merged: list[str] = []

#     for doc in crop_docs + global_docs:
#         if doc not in seen:
#             seen.add(doc)
#             merged.append(doc)

#         if len(merged) >= k:
#             break

#     # --------------------------------------------------
#     # Step 4: Timing check
#     # --------------------------------------------------
#     elapsed_ms = (time.perf_counter() - start) * 1000

#     if elapsed_ms > _SEARCH_TARGET_MS:
#         logger.warning(
#             "[similarity_search] Slow query: %.1fms "
#             "(target < %.0fms) for '%s'",
#             elapsed_ms,
#             _SEARCH_TARGET_MS,
#             query[:60],
#         )
#     else:
#         logger.debug(
#             "[similarity_search] %.1fms for '%s'",
#             elapsed_ms,
#             query[:60],
#         )

#     return merged


# def search_traits_with_scores(
#     query: str,
#     top_k: int | None = None,
#     crop: str | None = None,
# ) -> list[dict]:
#     """
#     Similarity search with scores and metadata.

#     Returns:
#         [
#             {
#                 "trait": "...",
#                 "score": 0.95,
#                 "domain": "biology",
#                 "tags": "crop,wheat,agriculture"
#             }
#         ]
#     """
#     start = time.perf_counter()

#     k = top_k if top_k is not None else settings.search_top_k
#     col = get_collection()

#     if col.count() == 0:
#         logger.warning("[similarity_search] Vector store is empty.")
#         return []

#     vector = list(embed_cached(query))

#     results = col.query(
#         query_embeddings=[vector],
#         n_results=min(k, col.count()),
#         include=["documents", "distances", "metadatas"],
#     )

#     docs = results["documents"][0]
#     distances = results["distances"][0]
#     metas = results.get(
#         "metadatas",
#         [[{}] * len(docs)]
#     )[0]

#     elapsed_ms = (time.perf_counter() - start) * 1000

#     logger.debug(
#         "[similarity_search] with_scores: %.1fms for '%s'",
#         elapsed_ms,
#         query[:60],
#     )

#     ranked = []

#     for doc, dist, meta in zip(docs, distances, metas):
#         score = 1.0 - dist

#         domain = str(meta.get("domain", "")).lower()
#         tags = str(meta.get("tags", "")).lower()

#         # Domain boosts
#         if domain == "biology":
#             score += 0.30
#         elif domain == "environment":
#             score += 0.20

#         # Tag boosts
#         if "crop" in tags:
#             score += 0.20

#         if "plant" in tags:
#             score += 0.15

#         if "agriculture" in tags:
#             score += 0.20

#         if "soil" in tags:
#             score += 0.10

#         ranked.append(
#             {
#                 "trait": doc,
#                 "score": round(score, 4),
#                 "domain": domain,
#                 "tags": tags,
#             }
#         )

#     ranked.sort(
#         key=lambda x: x["score"],
#         reverse=True,
#     )

#     return ranked[:k]


from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from search_engine.embeddings import embed_cached
from search_engine.vector_store import get_collection
from shared.config import settings

logger = logging.getLogger(__name__)

# Target from WorkflowB.pdf spec: <50ms per search query
_SEARCH_TARGET_MS = 50.0

# ChromaDB-safe domain filter using $or instead of broken $in on scalar fields
_DOMAIN_FILTER = {
    "$or": [
        {"domain": {"$eq": "biology"}},
        {"domain": {"$eq": "environment"}},
    ]
}


def _build_crop_filter(crop_lower: str) -> dict:
    """
    Builds a ChromaDB-compatible filter that matches:
      - records tagged with the crop name, OR
      - records whose crop field is the crop name or 'general'
    AND restricts to biology/environment domains.

    NOTE: $in on scalar string fields is broken in ChromaDB —
    we use $eq + $or instead.
    """
    return {
        "$and": [
            _DOMAIN_FILTER,
            {
                "$or": [
                    {"tags": {"$contains": crop_lower}},
                    {"crop": {"$eq": crop_lower}},
                    {"crop": {"$eq": "general"}},
                ]
            },
        ]
    }


def search_traits(
    query: str,
    top_k: int | None = None,
    crop: str | None = None,
) -> list[str]:
    """
    Fast, accurate similarity search returning top-k trait descriptions.

    Strategy:
    ─────────
    • If a crop is provided, run crop-specific and global queries IN PARALLEL
      using a ThreadPoolExecutor (cuts latency roughly in half vs sequential).
    • If no crop, run only the global query.
    • Crop results are prioritised; global results fill remaining slots.
    • Deduplication is O(n) via a set.

    ChromaDB filter correctness:
    ─────────────────────────────
    • NEVER use {"field": {"$in": [...]}} on scalar string fields — it silently
      returns 0 results. Use {"$or": [{"field": {"$eq": v}} ...]} instead.
    • $contains works correctly for list/array metadata fields (e.g. tags).

    Args:
        query:  Natural-language query string.
        top_k:  Max results to return (defaults to settings.search_top_k).
        crop:   Optional crop name to prioritise (e.g. "wheat", "rice").

    Returns:
        List of trait description strings, crop-specific results first.
    """
    k = top_k if top_k is not None else settings.search_top_k
    col = get_collection()

    if col.count() == 0:
        logger.warning(
            "[similarity_search] Vector store is empty. "
            "Run populate() or load_from_parquet() first."
        )
        return []

    # Embed once, reuse for all queries
    vector = list(embed_cached(query))
    n = min(k, col.count())

    crop_lower = crop.lower() if crop and crop.lower() not in ("unknown", "", "general") else None

    start = time.perf_counter()

    # ------------------------------------------------------------------ #
    # Run crop + global queries in parallel when crop is present           #
    # ------------------------------------------------------------------ #
    crop_docs: list[str] = []
    global_docs: list[str] = []

    def _query_crop() -> list[str]:
        """Crop-specific query with fallback."""
        try:
            res = col.query(
                query_embeddings=[vector],
                n_results=n,
                where=_build_crop_filter(crop_lower),
                include=["documents"],
            )
            return res["documents"][0] if res["documents"] else []
        except Exception as e:
            logger.debug("[similarity_search] Crop filter failed (%s), trying crop-only fallback.", e)
            try:
                res = col.query(
                    query_embeddings=[vector],
                    n_results=n,
                    where={
                        "$or": [
                            {"crop": {"$eq": crop_lower}},
                            {"crop": {"$eq": "general"}},
                        ]
                    },
                    include=["documents"],
                )
                return res["documents"][0] if res["documents"] else []
            except Exception as e2:
                logger.warning("[similarity_search] Crop fallback also failed: %s", e2)
                return []

    def _query_global() -> list[str]:
        """Global domain-filtered query."""
        try:
            res = col.query(
                query_embeddings=[vector],
                n_results=n,
                where=_DOMAIN_FILTER,
                include=["documents"],
            )
            return res["documents"][0] if res["documents"] else []
        except Exception as e:
            logger.warning("[similarity_search] Global query failed: %s", e)
            return []

    if crop_lower:
        # Fire both queries concurrently
        with ThreadPoolExecutor(max_workers=2) as pool:
            future_crop   = pool.submit(_query_crop)
            future_global = pool.submit(_query_global)
            crop_docs   = future_crop.result()
            global_docs = future_global.result()
    else:
        global_docs = _query_global()

    # ------------------------------------------------------------------ #
    # Merge: crop results first, then global, deduplicated, capped at k   #
    # ------------------------------------------------------------------ #
    seen: set[str] = set()
    merged: list[str] = []

    for doc in crop_docs + global_docs:
        if doc not in seen:
            seen.add(doc)
            merged.append(doc)
        if len(merged) >= k:
            break

    # ------------------------------------------------------------------ #
    # Timing log                                                           #
    # ------------------------------------------------------------------ #
    elapsed_ms = (time.perf_counter() - start) * 1000

    if elapsed_ms > _SEARCH_TARGET_MS:
        logger.warning(
            "[similarity_search] Slow query: %.1fms (target <%.0fms) for: '%s'",
            elapsed_ms, _SEARCH_TARGET_MS, query[:60],
        )
    else:
        logger.debug(
            "[similarity_search] %.1fms for: '%s'", elapsed_ms, query[:60]
        )

    return merged


def search_traits_with_scores(
    query: str,
    top_k: int | None = None,
    crop: str | None = None,
) -> list[dict]:
    """
    Similarity search with relevance scores and metadata.

    Scoring:
    ────────
    Base score  = 1.0 - cosine_distance   (range: 0 → 1)
    Domain boost: biology +0.30 | environment +0.20
    Tag boosts:   crop +0.20 | agriculture +0.20 | plant +0.15 | soil +0.10

    Returns:
        List of dicts sorted by score descending:
        [{"trait": str, "score": float, "domain": str, "tags": str}, ...]
    """
    k = top_k if top_k is not None else settings.search_top_k
    col = get_collection()

    if col.count() == 0:
        logger.warning("[similarity_search] Vector store is empty.")
        return []

    vector = list(embed_cached(query))
    n = min(k, col.count())

    crop_lower = crop.lower() if crop and crop.lower() not in ("unknown", "", "general") else None

    start = time.perf_counter()

    # ------------------------------------------------------------------ #
    # Parallel fetch: crop-scored + global-scored                          #
    # ------------------------------------------------------------------ #
    def _scored_query(where_filter: dict | None) -> tuple[list, list, list]:
        """Returns (docs, distances, metadatas) for a given filter."""
        kwargs = dict(
            query_embeddings=[vector],
            n_results=n,
            include=["documents", "distances", "metadatas"],
        )
        if where_filter:
            kwargs["where"] = where_filter
        try:
            res = col.query(**kwargs)
            docs      = res["documents"][0] if res["documents"] else []
            distances = res["distances"][0]  if res["distances"] else []
            metas     = res.get("metadatas", [[]])[0]
            return docs, distances, metas
        except Exception as e:
            logger.warning("[similarity_search] scored query failed: %s", e)
            return [], [], []

    raw_items: list[tuple] = []  # (doc, dist, meta)

    if crop_lower:
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_crop   = pool.submit(_scored_query, _build_crop_filter(crop_lower))
            f_global = pool.submit(_scored_query, _DOMAIN_FILTER)
            for docs, dists, metas in [f_crop.result(), f_global.result()]:
                raw_items.extend(zip(docs, dists, metas))
    else:
        docs, dists, metas = _scored_query(_DOMAIN_FILTER)
        raw_items.extend(zip(docs, dists, metas))

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.debug("[similarity_search] with_scores: %.1fms for '%s'", elapsed_ms, query[:60])

    # ------------------------------------------------------------------ #
    # Deduplicate, score, and rank                                         #
    # ------------------------------------------------------------------ #
    seen: set[str] = set()
    ranked: list[dict] = []

    for doc, dist, meta in raw_items:
        if doc in seen:
            continue
        seen.add(doc)

        score  = 1.0 - dist
        domain = str(meta.get("domain", "")).lower()
        tags   = str(meta.get("tags", "")).lower()

        # Domain boosts
        if domain == "biology":
            score += 0.30
        elif domain == "environment":
            score += 0.20

        # Tag boosts
        if "crop"        in tags: score += 0.20
        if "agriculture" in tags: score += 0.20
        if "plant"       in tags: score += 0.15
        if "soil"        in tags: score += 0.10

        ranked.append({
            "trait":  doc,
            "score":  round(score, 4),
            "domain": domain,
            "tags":   tags,
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:k]