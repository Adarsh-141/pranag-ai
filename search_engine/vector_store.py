"""
ChromaDB vector store wrapper — Jay's Task 2 + Task 7

Handles universal_index_final.parquet — the actual Parquet file from Kartik.

PARQUET FILE STRUCTURE (universal_index_final.parquet — 254,671 rows, 25MB):
  Columns : entity_id, domain, name, description,
            key_prop_1, key_prop_2, key_prop_3,
            source, source_id, tags
  Domains : chemistry(110k), biology(107k), physics(21k),
            materials(10k), environment(6.5k)
  Sources : PubChem(100k), GBIF(45k), USGS(20k), Gene Ontology(13k),
            Cell Ontology(13k), PDB(10k), ChEMBL(10k),
            Materials Project(10k), iNaturalist(10k), NCBI Gene(9.5k),
            SoilGrids/ISRIC(4.5k — India soil), AgriStack(1.9k — India crops)
  Relevant: 36,846 rows tagged agriculture/crop/india/plant/soil
  Best for PRANA-G: AgriStack (India crop yield), SoilGrids (India soil),
                    NCBI Gene (genetics), Gene Ontology (biology)

EMBEDDING STRATEGY:
  text = name + '. ' + description  (avg 260 chars, max 2202)
  Stored metadata: domain, tags (used for filtering in similarity_search)
  entity_id cleaned: 6 IDs have slashes — replaced with underscores

Changes over GitHub version:
  • load_from_parquet() — loads the actual parquet correctly in batches of 500
  • Fixes 6 bad entity_ids (slashes in IDs) before upserting to ChromaDB
  • get_stats() — shows entities loaded vs 525M target
  • health_check() — verifies store is ready before queries run
  • populate() and SEED_TRAITS unchanged for dev/testing without parquet
"""
from __future__ import annotations

import logging
import os
import re

import chromadb

from shared.config import settings
from search_engine.embeddings import embed_batch

logger = logging.getLogger(__name__)

_client = None
_collection = None


def _make_client():
    return chromadb.PersistentClient(
        path="./chroma_db"
    )


_client = None
_collection = None

def get_collection():
    global _client, _collection

    if _collection is None:
        _client = chromadb.PersistentClient(
            path="./chroma_db"
        )

        _collection = _client.get_collection(
            name="entities"
        )

    return _collection


# ── Seed traits (47 entries — for dev/testing without the Parquet file) ───────

SEED_TRAITS: list[dict] = [
    {"id": "w001", "crop": "wheat", "domain": "biology",
     "text": "heat shock protein HSP70 expression increases wheat survival above 45 degrees C"},
    {"id": "w002", "crop": "wheat", "domain": "biology",
     "text": "drought resistance in wheat via stomata closure and reduced transpiration"},
    {"id": "w003", "crop": "wheat", "domain": "biology",
     "text": "high canopy temperature tolerance in wheat cultivar HD3086"},
    {"id": "w004", "crop": "wheat", "domain": "biology",
     "text": "grain filling rate in wheat stable between 35 and 42 degrees C ambient temperature"},
    {"id": "w005", "crop": "wheat", "domain": "biology",
     "text": "tiller production in wheat maintained under moderate heat stress"},
    {"id": "w006", "crop": "wheat", "domain": "biology",
     "text": "rust resistance genes Lr34 Yr36 for wheat leaf and yellow rust"},
    {"id": "w007", "crop": "wheat", "domain": "biology",
     "text": "deep root architecture in wheat reaching 120cm for subsoil moisture access"},
    {"id": "w008", "crop": "wheat", "domain": "biology",
     "text": "osmotic adjustment in wheat through proline accumulation under water deficit"},
    {"id": "s001", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane heat tolerance variety Co0238 performs well at 35-42 degrees C in Uttar Pradesh"},
    {"id": "s002", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane sucrose accumulation maintained under moderate heat stress 37-40 degrees C"},
    {"id": "s003", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane ratoon crop regeneration under high temperature conditions"},
    {"id": "s004", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane waterlogging tolerance important for Uttar Pradesh monsoon flooding"},
    {"id": "s005", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane drought tolerance through deep fibrous root system and osmotic regulation"},
    {"id": "s006", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane red rot resistance Colletotrichum falcatum fungal pathogen management"},
    {"id": "s007", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane high CCS sugar content varieties for UP subtropical growing conditions"},
    {"id": "s008", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane early maturing variety 10 month crop cycle for North Indian plains"},
    {"id": "s009", "crop": "sugarcane", "domain": "environment",
     "text": "sugarcane alluvial soil preference Gangetic plains Uttar Pradesh high fertility loamy"},
    {"id": "s010", "crop": "sugarcane", "domain": "environment",
     "text": "sugarcane cultivation Uttar Pradesh Meerut Muzaffarnagar belt subtropical climate"},
    {"id": "s011", "crop": "sugarcane", "domain": "chemistry",
     "text": "sugarcane photosynthesis C4 pathway efficient at high temperatures 30-40 degrees C"},
    {"id": "s012", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane smut resistance Sporisorium scitamineum whip emergence control"},
    {"id": "s013", "crop": "sugarcane", "domain": "biology",
     "text": "sugarcane high tillering ability after planting improves yield in North India"},
    {"id": "s014", "crop": "sugarcane", "domain": "materials",
     "text": "sugarcane bagasse and trash mulching conserves soil moisture reduces evaporation"},
    {"id": "r001", "crop": "rice", "domain": "biology",
     "text": "rice submergence tolerance Sub1A gene flood survival 2 weeks waterlogged"},
    {"id": "r002", "crop": "rice", "domain": "biology",
     "text": "rice heat tolerance during flowering pollen viability above 38 degrees C"},
    {"id": "r003", "crop": "rice", "domain": "biology",
     "text": "rice salinity tolerance Saltol QTL for coastal and saline soils"},
    {"id": "r004", "crop": "rice", "domain": "environment",
     "text": "rice paddy cultivation kharif season high rainfall alluvial soils India"},
    {"id": "m001", "crop": "maize", "domain": "biology",
     "text": "maize drought tolerance stay-green trait delayed senescence under water stress"},
    {"id": "m002", "crop": "maize", "domain": "biology",
     "text": "maize heat stress tolerance pollen germination maintained above 38 degrees C"},
    {"id": "m003", "crop": "maize", "domain": "chemistry",
     "text": "maize C4 photosynthesis high efficiency at elevated temperatures and CO2"},
    {"id": "b001", "crop": "bajra", "domain": "biology",
     "text": "bajra pearl millet extreme heat tolerance above 42 degrees C arid Rajasthan Gujarat"},
    {"id": "b002", "crop": "bajra", "domain": "environment",
     "text": "bajra sandy soil low fertility drought adaptation Rajasthan desert conditions"},
    {"id": "mu01", "crop": "mustard", "domain": "biology",
     "text": "mustard heat tolerance during pod filling Rajasthan Haryana rabi season"},
    {"id": "mu02", "crop": "mustard", "domain": "biology",
     "text": "mustard aphid resistance high glucosinolate content natural pest deterrent"},
    {"id": "c001", "crop": "cotton", "domain": "biology",
     "text": "cotton heat tolerance boll development above 40 degrees C Maharashtra Gujarat Telangana"},
    {"id": "c002", "crop": "cotton", "domain": "biology",
     "text": "Bt cotton bollworm resistance Cry1Ac gene expression pest management"},
    {"id": "p001", "crop": "general", "domain": "chemistry",
     "text": "Arrhenius rate adaptation enzymes stable 40-55 degrees C temperature range crop metabolism"},
    {"id": "p002", "crop": "general", "domain": "biology",
     "text": "antioxidant enzyme SOD CAT activity elevated under oxidative heat stress all crops"},
    {"id": "p003", "crop": "general", "domain": "chemistry",
     "text": "phytohormone ABA abscisic acid signalling pathway regulates drought response"},
    {"id": "p004", "crop": "general", "domain": "biology",
     "text": "early vigour germination within 48h at 35-45 degrees C soil temperature for crop establishment"},
    {"id": "p005", "crop": "general", "domain": "materials",
     "text": "waxy leaf cuticle coating reduces UV radiation and water loss in heat stress"},
    {"id": "e001", "crop": "general", "domain": "environment",
     "text": "arid zone adaptation Jodhpur Barmer Bikaner Rajasthan low rainfall desert crops"},
    {"id": "e002", "crop": "general", "domain": "environment",
     "text": "alluvial fertile soil Gangetic plains Uttar Pradesh Bihar high productivity agriculture"},
    {"id": "e003", "crop": "general", "domain": "environment",
     "text": "salinity tolerance sandy loam soils pH 7.5-8.5 Rajasthan alkaline conditions"},
    {"id": "e004", "crop": "general", "domain": "environment",
     "text": "high humidity subtropical climate 70-80 percent monsoon season North Indian plains"},
    {"id": "e005", "crop": "general", "domain": "environment",
     "text": "photosynthetic efficiency under high solar radiation and heat stress tropical crops"},
    {"id": "e006", "crop": "general", "domain": "biology",
     "text": "thick seed coat protects embryo from thermal and osmotic stress germination"},
    {"id": "e007", "crop": "general", "domain": "biology",
     "text": "nitrogen use efficiency optimised nitrate transporter expression high yield potential"},
]


def _clean_id(entity_id: str) -> str:
    """
    Fix the 6 entity_ids in universal_index_final.parquet that contain
    slashes or other characters ChromaDB does not allow in document IDs.
    Replaces / and whitespace with underscore.
    """
    return re.sub(r"[\s/]", "_", str(entity_id))


def populate(force: bool = False) -> None:
    """
    Seed the vector store with 47 hardcoded SEED_TRAITS.
    Used for dev/testing when universal_index_final.parquet is not available.
    Skips if already populated unless force=True.
    """
    col = get_collection()
    if col.count() > 0 and not force:
        logger.info("[vector_store] Already populated (%d entities). Skipping seed.", col.count())
        return

    texts   = [t["text"]   for t in SEED_TRAITS]
    ids     = [t["id"]     for t in SEED_TRAITS]
    metas   = [{"domain": t["domain"], "crop": t["crop"], "tags": ""} for t in SEED_TRAITS]
    vectors = [v.tolist() for v in embed_batch(texts)]

    col.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metas)
    logger.info("[vector_store] Seeded %d traits.", len(SEED_TRAITS))
    print(f"[vector_store] Seeded {len(SEED_TRAITS)} traits ({len({t['crop'] for t in SEED_TRAITS})} crops).")


def load_from_parquet(parquet_path: str, force: bool = False) -> int:
    """
    Jay Task 2 — Load universal_index_final.parquet into ChromaDB.

    Processes 254,671 rows in batches of 500.
    Builds embedding text as: name + '. ' + description
    Stores domain and tags as metadata for search filtering.
    Fixes 6 entity_ids that contain slashes (ChromaDB disallows them).

    Args:
        parquet_path: Path to universal_index_final.parquet
        force:        Reload even if store already has data

    Returns:
        Number of entities successfully loaded

    Usage (run once after cloning):
        python -c "
        from search_engine.vector_store import load_from_parquet
        load_from_parquet('universal_index_final.parquet')
        "
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required: pip install pandas pyarrow")

    if not os.path.exists(parquet_path):
        logger.error("[vector_store] File not found: %s", parquet_path)
        print(f"[vector_store] ERROR: {parquet_path} not found.")
        print("  Put universal_index_final.parquet in the project root folder.")
        return 0

    col = get_collection()
    if col.count() > 47 and not force:
        logger.info("[vector_store] Parquet already loaded (%d entities).", col.count())
        return col.count()

    df = pd.read_parquet(parquet_path)
    logger.info("[vector_store] Parquet loaded: %d rows.", len(df))

    # Validate columns
    required = {"entity_id", "domain", "name", "description"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing columns: {missing}. Found: {list(df.columns)}")

    # Build embedding text
    df["_text"] = (
        df["name"].fillna("").str.strip()
        + ". "
        + df["description"].fillna("").str.strip()
    )

    # Fix 6 bad entity_ids (slashes — ChromaDB disallows them)
    df["_clean_id"] = df["entity_id"].apply(_clean_id)

    # Basic cleaning
    df = df[df["_text"].str.len() >= 10]
    df = df.drop_duplicates(subset=["_clean_id"], keep="first")

    total      = len(df)
    BATCH_SIZE = 500
    loaded     = 0

    logger.info("[vector_store] Loading %d entities into ChromaDB in batches of %d...",
                total, BATCH_SIZE)

    for i in range(0, total, BATCH_SIZE):
        batch = df.iloc[i: i + BATCH_SIZE]

        texts   = batch["_text"].tolist()
        ids     = batch["_clean_id"].tolist()
        metas   = [
            {
                "domain": str(row.get("domain", "biology")),
                "tags":   str(row.get("tags",   "")),
                "crop":   "general",   # Parquet uses tags not crop column
            }
            for _, row in batch.iterrows()
        ]
        vectors = [v.tolist() for v in embed_batch(texts)]

        col.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metas)
        loaded += len(batch)

        if loaded % 5000 == 0 or loaded == total:
            print(f"[vector_store] {loaded:,} / {total:,} entities loaded...", end="\r", flush=True)

    print(f"\n[vector_store] Done. {loaded:,} entities from {parquet_path}")
    logger.info("[vector_store] Load complete: %d entities.", loaded)
    return loaded


def get_stats() -> dict:
    """
    Jay Task 7 — Current database state vs the 525M entity target.

    Usage:
        from search_engine.vector_store import get_stats
        print(get_stats())
    """
    col    = get_collection()
    count  = col.count()
    target = 525_000_000
    return {
        "total_entities":  count,
        "target":          target,
        "gap":             max(0, target - count),
        "coverage":        f"{count / target * 100:.4f}%",
        "parquet_loaded":  count > 47,
        "note": (
            "47 dev seed traits. Run load_from_parquet('universal_index_final.parquet') to load real data."
            if count <= 47
            else f"{count:,} entities loaded from Parquet. Full 525M target needs Kartik's full dataset."
        ),
    }


def health_check() -> dict:
    """
    Jay Task 7 — Verify store is ready before queries run.

    Usage:
        from search_engine.vector_store import health_check
        s = health_check()
        if s['status'] == 'empty': populate()
    """
    col   = get_collection()
    count = col.count()
    return {
        "status":  "ready" if count > 0 else "empty",
        "count":   count,
        "message": (
            f"{count:,} entities loaded — ready for search."
            if count > 0
            else "Empty. Call populate() for dev mode or load_from_parquet() for real data."
        ),
    }
