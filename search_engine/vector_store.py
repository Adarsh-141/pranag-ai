# """
# ChromaDB vector store wrapper — Jay's Task 2 + Task 7

# Handles universal_index_final.parquet — the actual Parquet file from Kartik.

# PARQUET FILE STRUCTURE (universal_index_final.parquet — 254,671 rows, 25MB):
#   Columns : entity_id, domain, name, description,
#             key_prop_1, key_prop_2, key_prop_3,
#             source, source_id, tags
#   Domains : chemistry(110k), biology(107k), physics(21k),
#             materials(10k), environment(6.5k)
#   Sources : PubChem(100k), GBIF(45k), USGS(20k), Gene Ontology(13k),
#             Cell Ontology(13k), PDB(10k), ChEMBL(10k),
#             Materials Project(10k), iNaturalist(10k), NCBI Gene(9.5k),
#             SoilGrids/ISRIC(4.5k — India soil), AgriStack(1.9k — India crops)
#   Relevant: 36,846 rows tagged agriculture/crop/india/plant/soil
#   Best for PRANA-G: AgriStack (India crop yield), SoilGrids (India soil),
#                     NCBI Gene (genetics), Gene Ontology (biology)

# EMBEDDING STRATEGY:
#   text = name + '. ' + description  (avg 260 chars, max 2202)
#   Stored metadata: domain, tags (used for filtering in similarity_search)
#   entity_id cleaned: 6 IDs have slashes — replaced with underscores

# Changes over GitHub version:
#   • load_from_parquet() — loads the actual parquet correctly in batches of 500
#   • Fixes 6 bad entity_ids (slashes in IDs) before upserting to ChromaDB
#   • get_stats() — shows entities loaded vs 525M target
#   • health_check() — verifies store is ready before queries run
#   • populate() and SEED_TRAITS unchanged for dev/testing without parquet
# """
# from __future__ import annotations

# import logging
# import os
# import re

# import chromadb

# from shared.config import settings
# from search_engine.embeddings import embed_batch

# logger = logging.getLogger(__name__)

# _client = None
# _collection = None


# def _make_client():
#     return chromadb.PersistentClient(
#         path="./chroma_db"
#     )


# _client = None
# _collection = None

# def get_collection():
#     global _client, _collection

#     if _collection is None:
#         _client = chromadb.PersistentClient(
#             path="./chroma_db"
#         )

#         _collection = _client.get_collection(
#             name="entities"
#         )

#     return _collection


# # ── Seed traits (47 entries — for dev/testing without the Parquet file) ───────

# SEED_TRAITS: list[dict] = [
#     {"id": "w001", "crop": "wheat", "domain": "biology",
#      "text": "heat shock protein HSP70 expression increases wheat survival above 45 degrees C"},
#     {"id": "w002", "crop": "wheat", "domain": "biology",
#      "text": "drought resistance in wheat via stomata closure and reduced transpiration"},
#     {"id": "w003", "crop": "wheat", "domain": "biology",
#      "text": "high canopy temperature tolerance in wheat cultivar HD3086"},
#     {"id": "w004", "crop": "wheat", "domain": "biology",
#      "text": "grain filling rate in wheat stable between 35 and 42 degrees C ambient temperature"},
#     {"id": "w005", "crop": "wheat", "domain": "biology",
#      "text": "tiller production in wheat maintained under moderate heat stress"},
#     {"id": "w006", "crop": "wheat", "domain": "biology",
#      "text": "rust resistance genes Lr34 Yr36 for wheat leaf and yellow rust"},
#     {"id": "w007", "crop": "wheat", "domain": "biology",
#      "text": "deep root architecture in wheat reaching 120cm for subsoil moisture access"},
#     {"id": "w008", "crop": "wheat", "domain": "biology",
#      "text": "osmotic adjustment in wheat through proline accumulation under water deficit"},
#     {"id": "s001", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane heat tolerance variety Co0238 performs well at 35-42 degrees C in Uttar Pradesh"},
#     {"id": "s002", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane sucrose accumulation maintained under moderate heat stress 37-40 degrees C"},
#     {"id": "s003", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane ratoon crop regeneration under high temperature conditions"},
#     {"id": "s004", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane waterlogging tolerance important for Uttar Pradesh monsoon flooding"},
#     {"id": "s005", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane drought tolerance through deep fibrous root system and osmotic regulation"},
#     {"id": "s006", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane red rot resistance Colletotrichum falcatum fungal pathogen management"},
#     {"id": "s007", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane high CCS sugar content varieties for UP subtropical growing conditions"},
#     {"id": "s008", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane early maturing variety 10 month crop cycle for North Indian plains"},
#     {"id": "s009", "crop": "sugarcane", "domain": "environment",
#      "text": "sugarcane alluvial soil preference Gangetic plains Uttar Pradesh high fertility loamy"},
#     {"id": "s010", "crop": "sugarcane", "domain": "environment",
#      "text": "sugarcane cultivation Uttar Pradesh Meerut Muzaffarnagar belt subtropical climate"},
#     {"id": "s011", "crop": "sugarcane", "domain": "chemistry",
#      "text": "sugarcane photosynthesis C4 pathway efficient at high temperatures 30-40 degrees C"},
#     {"id": "s012", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane smut resistance Sporisorium scitamineum whip emergence control"},
#     {"id": "s013", "crop": "sugarcane", "domain": "biology",
#      "text": "sugarcane high tillering ability after planting improves yield in North India"},
#     {"id": "s014", "crop": "sugarcane", "domain": "materials",
#      "text": "sugarcane bagasse and trash mulching conserves soil moisture reduces evaporation"},
#     {"id": "r001", "crop": "rice", "domain": "biology",
#      "text": "rice submergence tolerance Sub1A gene flood survival 2 weeks waterlogged"},
#     {"id": "r002", "crop": "rice", "domain": "biology",
#      "text": "rice heat tolerance during flowering pollen viability above 38 degrees C"},
#     {"id": "r003", "crop": "rice", "domain": "biology",
#      "text": "rice salinity tolerance Saltol QTL for coastal and saline soils"},
#     {"id": "r004", "crop": "rice", "domain": "environment",
#      "text": "rice paddy cultivation kharif season high rainfall alluvial soils India"},
#     {"id": "m001", "crop": "maize", "domain": "biology",
#      "text": "maize drought tolerance stay-green trait delayed senescence under water stress"},
#     {"id": "m002", "crop": "maize", "domain": "biology",
#      "text": "maize heat stress tolerance pollen germination maintained above 38 degrees C"},
#     {"id": "m003", "crop": "maize", "domain": "chemistry",
#      "text": "maize C4 photosynthesis high efficiency at elevated temperatures and CO2"},
#     {"id": "b001", "crop": "bajra", "domain": "biology",
#      "text": "bajra pearl millet extreme heat tolerance above 42 degrees C arid Rajasthan Gujarat"},
#     {"id": "b002", "crop": "bajra", "domain": "environment",
#      "text": "bajra sandy soil low fertility drought adaptation Rajasthan desert conditions"},
#     {"id": "mu01", "crop": "mustard", "domain": "biology",
#      "text": "mustard heat tolerance during pod filling Rajasthan Haryana rabi season"},
#     {"id": "mu02", "crop": "mustard", "domain": "biology",
#      "text": "mustard aphid resistance high glucosinolate content natural pest deterrent"},
#     {"id": "c001", "crop": "cotton", "domain": "biology",
#      "text": "cotton heat tolerance boll development above 40 degrees C Maharashtra Gujarat Telangana"},
#     {"id": "c002", "crop": "cotton", "domain": "biology",
#      "text": "Bt cotton bollworm resistance Cry1Ac gene expression pest management"},
#     {"id": "p001", "crop": "general", "domain": "chemistry",
#      "text": "Arrhenius rate adaptation enzymes stable 40-55 degrees C temperature range crop metabolism"},
#     {"id": "p002", "crop": "general", "domain": "biology",
#      "text": "antioxidant enzyme SOD CAT activity elevated under oxidative heat stress all crops"},
#     {"id": "p003", "crop": "general", "domain": "chemistry",
#      "text": "phytohormone ABA abscisic acid signalling pathway regulates drought response"},
#     {"id": "p004", "crop": "general", "domain": "biology",
#      "text": "early vigour germination within 48h at 35-45 degrees C soil temperature for crop establishment"},
#     {"id": "p005", "crop": "general", "domain": "materials",
#      "text": "waxy leaf cuticle coating reduces UV radiation and water loss in heat stress"},
#     {"id": "e001", "crop": "general", "domain": "environment",
#      "text": "arid zone adaptation Jodhpur Barmer Bikaner Rajasthan low rainfall desert crops"},
#     {"id": "e002", "crop": "general", "domain": "environment",
#      "text": "alluvial fertile soil Gangetic plains Uttar Pradesh Bihar high productivity agriculture"},
#     {"id": "e003", "crop": "general", "domain": "environment",
#      "text": "salinity tolerance sandy loam soils pH 7.5-8.5 Rajasthan alkaline conditions"},
#     {"id": "e004", "crop": "general", "domain": "environment",
#      "text": "high humidity subtropical climate 70-80 percent monsoon season North Indian plains"},
#     {"id": "e005", "crop": "general", "domain": "environment",
#      "text": "photosynthetic efficiency under high solar radiation and heat stress tropical crops"},
#     {"id": "e006", "crop": "general", "domain": "biology",
#      "text": "thick seed coat protects embryo from thermal and osmotic stress germination"},
#     {"id": "e007", "crop": "general", "domain": "biology",
#      "text": "nitrogen use efficiency optimised nitrate transporter expression high yield potential"},
# ]


# def _clean_id(entity_id: str) -> str:
#     """
#     Fix the 6 entity_ids in universal_index_final.parquet that contain
#     slashes or other characters ChromaDB does not allow in document IDs.
#     Replaces / and whitespace with underscore.
#     """
#     return re.sub(r"[\s/]", "_", str(entity_id))


# def populate(force: bool = False) -> None:
#     """
#     Seed the vector store with 47 hardcoded SEED_TRAITS.
#     Used for dev/testing when universal_index_final.parquet is not available.
#     Skips if already populated unless force=True.
#     """
#     col = get_collection()
#     if col.count() > 0 and not force:
#         logger.info("[vector_store] Already populated (%d entities). Skipping seed.", col.count())
#         return

#     texts   = [t["text"]   for t in SEED_TRAITS]
#     ids     = [t["id"]     for t in SEED_TRAITS]
#     metas   = [{"domain": t["domain"], "crop": t["crop"], "tags": ""} for t in SEED_TRAITS]
#     vectors = [v.tolist() for v in embed_batch(texts)]

#     col.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metas)
#     logger.info("[vector_store] Seeded %d traits.", len(SEED_TRAITS))
#     print(f"[vector_store] Seeded {len(SEED_TRAITS)} traits ({len({t['crop'] for t in SEED_TRAITS})} crops).")


# def load_from_parquet(parquet_path: str, force: bool = False) -> int:
#     """
#     Jay Task 2 — Load universal_index_final.parquet into ChromaDB.

#     Processes 254,671 rows in batches of 500.
#     Builds embedding text as: name + '. ' + description
#     Stores domain and tags as metadata for search filtering.
#     Fixes 6 entity_ids that contain slashes (ChromaDB disallows them).

#     Args:
#         parquet_path: Path to universal_index_final.parquet
#         force:        Reload even if store already has data

#     Returns:
#         Number of entities successfully loaded

#     Usage (run once after cloning):
#         python -c "
#         from search_engine.vector_store import load_from_parquet
#         load_from_parquet('universal_index_final.parquet')
#         "
#     """
#     try:
#         import pandas as pd
#     except ImportError:
#         raise ImportError("pandas required: pip install pandas pyarrow")

#     if not os.path.exists(parquet_path):
#         logger.error("[vector_store] File not found: %s", parquet_path)
#         print(f"[vector_store] ERROR: {parquet_path} not found.")
#         print("  Put universal_index_final.parquet in the project root folder.")
#         return 0

#     col = get_collection()
#     if col.count() > 47 and not force:
#         logger.info("[vector_store] Parquet already loaded (%d entities).", col.count())
#         return col.count()

#     df = pd.read_parquet(parquet_path)
#     logger.info("[vector_store] Parquet loaded: %d rows.", len(df))

#     # Validate columns
#     required = {"entity_id", "domain", "name", "description"}
#     missing  = required - set(df.columns)
#     if missing:
#         raise ValueError(f"Parquet missing columns: {missing}. Found: {list(df.columns)}")

#     # Build embedding text
#     df["_text"] = (
#         df["name"].fillna("").str.strip()
#         + ". "
#         + df["description"].fillna("").str.strip()
#     )

#     # Fix 6 bad entity_ids (slashes — ChromaDB disallows them)
#     df["_clean_id"] = df["entity_id"].apply(_clean_id)

#     # Basic cleaning
#     df = df[df["_text"].str.len() >= 10]
#     df = df.drop_duplicates(subset=["_clean_id"], keep="first")

#     total      = len(df)
#     BATCH_SIZE = 500
#     loaded     = 0

#     logger.info("[vector_store] Loading %d entities into ChromaDB in batches of %d...",
#                 total, BATCH_SIZE)

#     for i in range(0, total, BATCH_SIZE):
#         batch = df.iloc[i: i + BATCH_SIZE]

#         texts   = batch["_text"].tolist()
#         ids     = batch["_clean_id"].tolist()
#         metas   = [
#             {
#                 "domain": str(row.get("domain", "biology")),
#                 "tags":   str(row.get("tags",   "")),
#                 "crop":   "general",   # Parquet uses tags not crop column
#             }
#             for _, row in batch.iterrows()
#         ]
#         vectors = [v.tolist() for v in embed_batch(texts)]

#         col.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metas)
#         loaded += len(batch)

#         if loaded % 5000 == 0 or loaded == total:
#             print(f"[vector_store] {loaded:,} / {total:,} entities loaded...", end="\r", flush=True)

#     print(f"\n[vector_store] Done. {loaded:,} entities from {parquet_path}")
#     logger.info("[vector_store] Load complete: %d entities.", loaded)
#     return loaded


# def get_stats() -> dict:
#     """
#     Jay Task 7 — Current database state vs the 525M entity target.

#     Usage:
#         from search_engine.vector_store import get_stats
#         print(get_stats())
#     """
#     col    = get_collection()
#     count  = col.count()
#     target = 525_000_000
#     return {
#         "total_entities":  count,
#         "target":          target,
#         "gap":             max(0, target - count),
#         "coverage":        f"{count / target * 100:.4f}%",
#         "parquet_loaded":  count > 47,
#         "note": (
#             "47 dev seed traits. Run load_from_parquet('universal_index_final.parquet') to load real data."
#             if count <= 47
#             else f"{count:,} entities loaded from Parquet. Full 525M target needs Kartik's full dataset."
#         ),
#     }


# def health_check() -> dict:
#     """
#     Jay Task 7 — Verify store is ready before queries run.

#     Usage:
#         from search_engine.vector_store import health_check
#         s = health_check()
#         if s['status'] == 'empty': populate()
#     """
#     col   = get_collection()
#     count = col.count()
#     return {
#         "status":  "ready" if count > 0 else "empty",
#         "count":   count,
#         "message": (
#             f"{count:,} entities loaded — ready for search."
#             if count > 0
#             else "Empty. Call populate() for dev mode or load_from_parquet() for real data."
#         ),
#     }


"""
Parquet-native vector store — replaces ChromaDB entirely.

WHAT CHANGED vs the ChromaDB version
─────────────────────────────────────
  Before:  parquet → embed → ChromaDB (upsert) → ChromaDB (query)
  Now:     parquet → embed → numpy matrix (.npy on disk) → cosine similarity

WHY
───
  ChromaDB added latency from its HTTP/persistence layer even in local mode.
  For 254k rows at 384 dims, the full vector matrix is ~370 MB in RAM —
  comfortably fits in memory and lets us do a batched cosine search in <50 ms.

DISK CACHE
──────────
  Embeddings are expensive to recompute (≈ 3–8 min for 254k rows on CPU).
  On first load, vectors are saved to  <parquet_path>.vectors.npy
  and the cleaned DataFrame to         <parquet_path>.clean.parquet
  Subsequent starts skip embedding and load from disk in ~1 second.

PUBLIC API  (same names as the ChromaDB version — nothing else needs changing)
──────────
  load_from_parquet(path, force=False) → int          # build/load the index
  similarity_search(query, n=10, domain=None) → list  # main search function
  get_stats() → dict
  health_check() → dict
  populate(force=False)                               # dev seed (unchanged)

LATER MIGRATION TO FAISS
─────────────────────────
  Step 1: pip install faiss-cpu
  Step 2: in _build_faiss_index() below, uncomment the FAISS block and
          comment out the numpy block.  Everything else stays the same.
"""
from __future__ import annotations

import logging
import os
import re

import numpy as np
import pandas as pd

from search_engine.embeddings import embed_batch, embed_cached

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────

_df: pd.DataFrame | None = None          # cleaned DataFrame (text + metadata)
_vectors: np.ndarray | None = None       # float32 matrix  [N × 384]  L2-normalised
_parquet_path: str | None = None         # path that produced the current state


# ── Internal helpers ──────────────────────────────────────────────────────────

def _cache_paths(parquet_path: str) -> tuple[str, str]:
    """Return (vectors_path, clean_df_path) derived from the parquet path."""
    base = parquet_path.rstrip(".parquet").rstrip(".parq")
    return base + ".vectors.npy", base + ".clean.parquet"


def _clean_id(entity_id: str) -> str:
    """Fix the 6 entity_ids in universal_index_final.parquet with slashes."""
    return re.sub(r"[\s/]", "_", str(entity_id))


def _cosine_search(
    query_vec: np.ndarray,
    matrix: np.ndarray,
    top_k: int,
    mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Batched cosine similarity search.

    Both query_vec and matrix rows must already be L2-normalised
    (embed_batch / embed_cached both set normalize_embeddings=True),
    so cosine similarity = dot product.

    Args:
        query_vec : (384,) float32 — already normalised
        matrix    : (N, 384) float32 — already normalised
        top_k     : number of results to return
        mask      : optional boolean array (N,) — True = include this row

    Returns:
        (scores, indices) — both shape (top_k,)
    """
    if mask is not None:
        scores_full = np.full(len(matrix), -2.0, dtype=np.float32)
        scores_full[mask] = matrix[mask] @ query_vec
    else:
        scores_full = matrix @ query_vec          # (N,) — one matmul, very fast

    top_k = min(top_k, int(mask.sum()) if mask is not None else len(matrix))
    indices = np.argpartition(scores_full, -top_k)[-top_k:]
    indices = indices[np.argsort(scores_full[indices])[::-1]]
    return scores_full[indices], indices


# ── Public API ────────────────────────────────────────────────────────────────

def load_from_parquet(parquet_path: str, force: bool = False) -> int:
    """
    Build (or reload from disk cache) the in-memory search index.

    First call  (~3–8 min on CPU for 254k rows):
      • Loads and cleans the parquet
      • Embeds all rows with embed_batch()
      • Saves vectors → <path>.vectors.npy
      • Saves cleaned df → <path>.clean.parquet

    Subsequent calls (~1 second):
      • Loads .npy and .clean.parquet from disk — skips embedding entirely

    Args:
        parquet_path : path to universal_index_final.parquet
        force        : re-embed even if cache exists

    Returns:
        number of rows indexed
    """
    global _df, _vectors, _parquet_path

    if not os.path.exists(parquet_path):
        print(f"[vector_store] ERROR: {parquet_path} not found.")
        return 0

    vec_path, df_path = _cache_paths(parquet_path)
    cache_exists = os.path.exists(vec_path) and os.path.exists(df_path)

    # ── Fast path: load from disk cache ──────────────────────────────────────
    if cache_exists and not force:
        print("[vector_store] Loading index from disk cache...")
        _df = pd.read_parquet(df_path)
        _vectors = np.load(vec_path)                    # memory-mapped by default
        _parquet_path = parquet_path
        print(f"[vector_store] Ready. {len(_df):,} entities loaded in ~1 second.")
        return len(_df)

    # ── Slow path: embed from scratch ─────────────────────────────────────────
    print("[vector_store] Building index from parquet (first-time setup)...")
    df = pd.read_parquet(parquet_path)
    logger.info("[vector_store] Parquet loaded: %d rows.", len(df))

    # Validate
    required = {"entity_id", "domain", "name", "description"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing columns: {missing}. Found: {list(df.columns)}")

    # Build text to embed  (same formula as ChromaDB version)
    df["_text"] = (
        df["name"].fillna("").str.strip()
        + ". "
        + df["description"].fillna("").str.strip()
    )
    df["_clean_id"] = df["entity_id"].apply(_clean_id)

    # Clean
    df = df[df["_text"].str.len() >= 10]
    df = df.drop_duplicates(subset=["_clean_id"], keep="first")
    df = df.reset_index(drop=True)

    total = len(df)
    print(f"[vector_store] Embedding {total:,} rows — this takes a few minutes on CPU...")

    # Embed in one call — embed_batch() handles internal batching + progress bar
    vectors = embed_batch(df["_text"].tolist(), batch_size=256)  # → (N, 384) float32
    vectors = np.array(vectors, dtype=np.float32)

    # Persist to disk so next start is instant
    np.save(vec_path, vectors)
    df.to_parquet(df_path, index=False)
    print(f"[vector_store] Index saved to {vec_path}")

    _df = df
    _vectors = vectors
    _parquet_path = parquet_path
    print(f"[vector_store] Done. {total:,} entities ready.")
    return total


def similarity_search(
    query: str,
    n: int = 10,
    domain: str | None = None,
) -> list[dict]:
    """
    Semantic search over the parquet index.

    Replaces ChromaDB's collection.query() — same output shape.

    Args:
        query  : natural-language query string
        n      : number of results to return (default 10)
        domain : optional filter — one of biology / chemistry / physics /
                 materials / environment / general

    Returns:
        list of dicts, each with keys:
          id, score, text, name, description, domain, tags, entity_id

    Usage:
        results = similarity_search("heat tolerant wheat variety", n=10)
        results = similarity_search("sugarcane soil", n=5, domain="environment")
    """
    if _vectors is None or _df is None:
        raise RuntimeError(
            "[vector_store] Index not loaded. "
            "Call load_from_parquet('universal_index_final.parquet') first."
        )

    # Embed query — uses lru_cache so repeated queries are instant
    query_vec = np.array(embed_cached(query), dtype=np.float32)

    # Build domain mask if requested
    mask: np.ndarray | None = None
    if domain:
        mask = (_df["domain"].str.lower() == domain.lower()).to_numpy()
        if mask.sum() == 0:
            logger.warning("[vector_store] domain='%s' matched 0 rows — ignoring filter.", domain)
            mask = None

    scores, indices = _cosine_search(query_vec, _vectors, top_k=n, mask=mask)

    results = []
    for score, idx in zip(scores, indices):
        row = _df.iloc[idx]
        results.append({
            "id":          row.get("_clean_id", str(idx)),
            "score":       float(score),
            "text":        row.get("_text", ""),
            "name":        row.get("name", ""),
            "description": row.get("description", ""),
            "domain":      row.get("domain", ""),
            "tags":        row.get("tags", ""),
            "entity_id":   row.get("entity_id", ""),
        })
    return results


def get_stats() -> dict:
    """Current index state vs the 525M entity target."""
    count = len(_df) if _df is not None else 0
    target = 525_000_000
    return {
        "total_entities": count,
        "target":         target,
        "gap":            max(0, target - count),
        "coverage":       f"{count / target * 100:.4f}%",
        "parquet_loaded": count > 47,
        "backend":        "numpy (parquet-native)",
        "note": (
            "47 dev seed traits active — call load_from_parquet() to load real data."
            if count <= 47
            else f"{count:,} entities loaded from parquet. Full 525M needs Kartik's full dataset."
        ),
    }


def health_check() -> dict:
    """Verify the index is ready before queries run."""
    count = len(_df) if _df is not None else 0
    return {
        "status":  "ready" if count > 0 else "empty",
        "count":   count,
        "backend": "numpy (parquet-native)",
        "message": (
            f"{count:,} entities loaded — ready for search."
            if count > 0
            else "Empty. Call populate() for dev mode or load_from_parquet() for real data."
        ),
    }


# ── Dev seed (unchanged — kept for testing without parquet) ───────────────────

SEED_TRAITS: list[dict] = [
    {"id": "w001", "crop": "wheat",     "domain": "biology",     "text": "heat shock protein HSP70 expression increases wheat survival above 45 degrees C"},
    {"id": "w002", "crop": "wheat",     "domain": "biology",     "text": "drought resistance in wheat via stomata closure and reduced transpiration"},
    {"id": "w003", "crop": "wheat",     "domain": "biology",     "text": "high canopy temperature tolerance in wheat cultivar HD3086"},
    {"id": "w004", "crop": "wheat",     "domain": "biology",     "text": "grain filling rate in wheat stable between 35 and 42 degrees C ambient temperature"},
    {"id": "w005", "crop": "wheat",     "domain": "biology",     "text": "tiller production in wheat maintained under moderate heat stress"},
    {"id": "w006", "crop": "wheat",     "domain": "biology",     "text": "rust resistance genes Lr34 Yr36 for wheat leaf and yellow rust"},
    {"id": "w007", "crop": "wheat",     "domain": "biology",     "text": "deep root architecture in wheat reaching 120cm for subsoil moisture access"},
    {"id": "w008", "crop": "wheat",     "domain": "biology",     "text": "osmotic adjustment in wheat through proline accumulation under water deficit"},
    {"id": "s001", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane heat tolerance variety Co0238 performs well at 35-42 degrees C in Uttar Pradesh"},
    {"id": "s002", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane sucrose accumulation maintained under moderate heat stress 37-40 degrees C"},
    {"id": "s003", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane ratoon crop regeneration under high temperature conditions"},
    {"id": "s004", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane waterlogging tolerance important for Uttar Pradesh monsoon flooding"},
    {"id": "s005", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane drought tolerance through deep fibrous root system and osmotic regulation"},
    {"id": "s006", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane red rot resistance Colletotrichum falcatum fungal pathogen management"},
    {"id": "s007", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane high CCS sugar content varieties for UP subtropical growing conditions"},
    {"id": "s008", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane early maturing variety 10 month crop cycle for North Indian plains"},
    {"id": "s009", "crop": "sugarcane", "domain": "environment", "text": "sugarcane alluvial soil preference Gangetic plains Uttar Pradesh high fertility loamy"},
    {"id": "s010", "crop": "sugarcane", "domain": "environment", "text": "sugarcane cultivation Uttar Pradesh Meerut Muzaffarnagar belt subtropical climate"},
    {"id": "s011", "crop": "sugarcane", "domain": "chemistry",   "text": "sugarcane photosynthesis C4 pathway efficient at high temperatures 30-40 degrees C"},
    {"id": "s012", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane smut resistance Sporisorium scitamineum whip emergence control"},
    {"id": "s013", "crop": "sugarcane", "domain": "biology",     "text": "sugarcane high tillering ability after planting improves yield in North India"},
    {"id": "s014", "crop": "sugarcane", "domain": "materials",   "text": "sugarcane bagasse and trash mulching conserves soil moisture reduces evaporation"},
    {"id": "r001", "crop": "rice",      "domain": "biology",     "text": "rice submergence tolerance Sub1A gene flood survival 2 weeks waterlogged"},
    {"id": "r002", "crop": "rice",      "domain": "biology",     "text": "rice heat tolerance during flowering pollen viability above 38 degrees C"},
    {"id": "r003", "crop": "rice",      "domain": "biology",     "text": "rice salinity tolerance Saltol QTL for coastal and saline soils"},
    {"id": "r004", "crop": "rice",      "domain": "environment", "text": "rice paddy cultivation kharif season high rainfall alluvial soils India"},
    {"id": "m001", "crop": "maize",     "domain": "biology",     "text": "maize drought tolerance stay-green trait delayed senescence under water stress"},
    {"id": "m002", "crop": "maize",     "domain": "biology",     "text": "maize heat stress tolerance pollen germination maintained above 38 degrees C"},
    {"id": "m003", "crop": "maize",     "domain": "chemistry",   "text": "maize C4 photosynthesis high efficiency at elevated temperatures and CO2"},
    {"id": "b001", "crop": "bajra",     "domain": "biology",     "text": "bajra pearl millet extreme heat tolerance above 42 degrees C arid Rajasthan Gujarat"},
    {"id": "b002", "crop": "bajra",     "domain": "environment", "text": "bajra sandy soil low fertility drought adaptation Rajasthan desert conditions"},
    {"id": "mu01", "crop": "mustard",   "domain": "biology",     "text": "mustard heat tolerance during pod filling Rajasthan Haryana rabi season"},
    {"id": "mu02", "crop": "mustard",   "domain": "biology",     "text": "mustard aphid resistance high glucosinolate content natural pest deterrent"},
    {"id": "c001", "crop": "cotton",    "domain": "biology",     "text": "cotton heat tolerance boll development above 40 degrees C Maharashtra Gujarat Telangana"},
    {"id": "c002", "crop": "cotton",    "domain": "biology",     "text": "Bt cotton bollworm resistance Cry1Ac gene expression pest management"},
    {"id": "p001", "crop": "general",   "domain": "chemistry",   "text": "Arrhenius rate adaptation enzymes stable 40-55 degrees C temperature range crop metabolism"},
    {"id": "p002", "crop": "general",   "domain": "biology",     "text": "antioxidant enzyme SOD CAT activity elevated under oxidative heat stress all crops"},
    {"id": "p003", "crop": "general",   "domain": "chemistry",   "text": "phytohormone ABA abscisic acid signalling pathway regulates drought response"},
    {"id": "p004", "crop": "general",   "domain": "biology",     "text": "early vigour germination within 48h at 35-45 degrees C soil temperature for crop establishment"},
    {"id": "p005", "crop": "general",   "domain": "materials",   "text": "waxy leaf cuticle coating reduces UV radiation and water loss in heat stress"},
    {"id": "e001", "crop": "general",   "domain": "environment", "text": "arid zone adaptation Jodhpur Barmer Bikaner Rajasthan low rainfall desert crops"},
    {"id": "e002", "crop": "general",   "domain": "environment", "text": "alluvial fertile soil Gangetic plains Uttar Pradesh Bihar high productivity agriculture"},
    {"id": "e003", "crop": "general",   "domain": "environment", "text": "salinity tolerance sandy loam soils pH 7.5-8.5 Rajasthan alkaline conditions"},
    {"id": "e004", "crop": "general",   "domain": "environment", "text": "high humidity subtropical climate 70-80 percent monsoon season North Indian plains"},
    {"id": "e005", "crop": "general",   "domain": "environment", "text": "photosynthetic efficiency under high solar radiation and heat stress tropical crops"},
    {"id": "e006", "crop": "general",   "domain": "biology",     "text": "thick seed coat protects embryo from thermal and osmotic stress germination"},
    {"id": "e007", "crop": "general",   "domain": "biology",     "text": "nitrogen use efficiency optimised nitrate transporter expression high yield potential"},
]


def populate(force: bool = False) -> None:
    """
    Seed the in-memory index with 47 hardcoded SEED_TRAITS.
    Used for dev/testing when universal_index_final.parquet is not available.
    Skips if already populated unless force=True.
    """
    global _df, _vectors

    if _df is not None and len(_df) > 0 and not force:
        logger.info("[vector_store] Already populated (%d entities). Skipping seed.", len(_df))
        return

    texts = [t["text"] for t in SEED_TRAITS]
    vectors = np.array(embed_batch(texts, batch_size=64), dtype=np.float32)

    _df = pd.DataFrame([
        {
            "_clean_id":   t["id"],
            "entity_id":   t["id"],
            "_text":       t["text"],
            "name":        t["text"][:40],
            "description": t["text"],
            "domain":      t["domain"],
            "tags":        "",
        }
        for t in SEED_TRAITS
    ])
    _vectors = vectors

    logger.info("[vector_store] Seeded %d traits.", len(SEED_TRAITS))
    print(f"[vector_store] Seeded {len(SEED_TRAITS)} traits ({len({t['crop'] for t in SEED_TRAITS})} crops).")