"""
Singleton embedding model — Jay's Task 1

Uses all-MiniLM-L6-v2 via Sentence Transformers.
All other modules import embed(), embed_batch(), embed_cached() from here.

Changes over GitHub version:
  • embed_cached() added with lru_cache(512) — Jay Task 7 (Performance Optimisation)
    Repeated identical queries skip the model entirely and return from memory.
    Returns a tuple (hashable) so lru_cache can store it.
  • embed_batch() added for fast bulk loading of Parquet data into ChromaDB.
    batch_size=64 balances memory and speed for 254k+ row datasets.
"""
from __future__ import annotations
import streamlit as st
from sentence_transformers import SentenceTransformer
import logging
from functools import lru_cache
import os
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
os.environ["HF_HUB_OFFLINE"] = "1" 
os.environ["TOKENIZERS_PARALLELISM"] = "false"

_model: SentenceTransformer | None = None

@st.cache_resource
def get_embedding_model():
    print("Loading embedding model into memory... (this should only happen once)")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # 2. Pre-warming: Run one dummy encode so PyTorch initializes internal kernels now
    model.encode(["warmup"]) 
    return model

# 2. Use the cached model for your embeddings
@lru_cache(maxsize=512)
def embed_cached(text: str):
    model = get_embedding_model()
    return model.encode([text])[0]

def _get_model() -> SentenceTransformer:
    """Load the embedding model once and reuse across all calls."""
    global _model
    if _model is None:
        logger.info("[embeddings] Loading SentenceTransformer (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("[embeddings] Model loaded.")
    return _model


def embed(text: str) -> np.ndarray:
    """
    Normalised L2 embedding for a single text string.
    Used for single queries at search time.
    """
    return _get_model().encode(text, normalize_embeddings=True)


def embed_batch(texts: list[str]) -> list[np.ndarray]:
    """
    Batch-encode a list of texts for fast vector-store population.
    Used when loading Parquet data from Kartik's universal_index_final.parquet.
    batch_size=64 keeps memory usage stable on large datasets.
    """
    return _get_model().encode(texts, normalize_embeddings=True, batch_size=64)


@lru_cache(maxsize=512)
def embed_cached(text: str) -> tuple[float, ...]:
    """
    Cached version of embed() for repeated identical queries.

    Jay Task 7 — Performance Optimisation:
      If the same query is made more than once (e.g. during workflow retries),
      this skips the model entirely and returns from memory.

    Returns a tuple (hashable) — convert back with list(embed_cached(text))
    before passing to ChromaDB.

    Cache size: 512 most-recent unique queries.
    """
    return tuple(
        _get_model().encode(text, normalize_embeddings=True).tolist()
    )
