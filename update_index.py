"""
update_index.py — Incremental index update

When new rows are added to the parquet file, run this instead of run_once.py.
It only embeds the NEW rows — existing embeddings are reused as-is.

Run from your Prompt_Parser folder:
    python update_index.py

How it works:
    1. Load existing .clean.parquet  → get list of already-embedded entity_ids
    2. Load new parquet file         → find rows whose entity_id is NOT in the list
    3. Embed only those new rows
    4. Append new vectors to existing .npy
    5. Append new rows to existing .clean.parquet
    Done — existing embeddings untouched.
"""
import os
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# ── Path config (must match run_once.py and app.py) ──────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PARQUET_PATH = os.path.normpath(os.path.join(
    BASE_DIR, "..", "PINN Framework", "datasrc", "universal_index_final.parquet"
))

base         = PARQUET_PATH.replace(".parquet", "")
VECTORS_PATH = base + ".vectors.npy"
CLEAN_PATH   = base + ".clean.parquet"
CHECKPOINT   = base + ".update_checkpoint.npy"

BATCH_SIZE       = 512
CHECKPOINT_EVERY = 50

# ── Check cache exists (run run_once.py first if not) ────────────────────────
if not os.path.exists(VECTORS_PATH) or not os.path.exists(CLEAN_PATH):
    print("❌ No existing index found.")
    print("   Run run_once.py first to build the initial index.")
    print("   Then use update_index.py for future additions.")
    exit(1)

# ── Load existing index ───────────────────────────────────────────────────────
print("Loading existing index...")
existing_df      = pd.read_parquet(CLEAN_PATH)
existing_vectors = np.load(VECTORS_PATH)
existing_ids     = set(existing_df["entity_id"].astype(str).tolist())

print(f"  Existing index: {len(existing_df):,} rows, {existing_vectors.shape} vectors")

# ── Load new parquet and find new rows ───────────────────────────────────────
print(f"\nLoading new parquet from:\n  {PARQUET_PATH}")
new_df = pd.read_parquet(PARQUET_PATH)

# Build text column (same formula as run_once.py and vector_store.py)
new_df["_text"] = (
    new_df["name"].fillna("").str.strip()
    + ". "
    + new_df["description"].fillna("").str.strip()
)
new_df = new_df[new_df["_text"].str.len() >= 10].reset_index(drop=True)

# Find rows not already in the index
new_df["entity_id"] = new_df["entity_id"].astype(str)
truly_new = new_df[~new_df["entity_id"].isin(existing_ids)].reset_index(drop=True)

print(f"  New parquet total rows : {len(new_df):,}")
print(f"  Already in index       : {len(existing_ids):,}")
print(f"  New rows to embed      : {len(truly_new):,}")

if len(truly_new) == 0:
    print("\n✅ Nothing new to embed — index is already up to date.")
    exit(0)

# ── Load checkpoint if interrupted mid-update ─────────────────────────────────
if os.path.exists(CHECKPOINT):
    partial = np.load(CHECKPOINT)
    start_row = len(partial)
    new_vectors = list(partial)
    print(f"\n⚡ Resuming update from row {start_row:,} / {len(truly_new):,}")
else:
    start_row = 0
    new_vectors = []
    print(f"\nStarting fresh update — embedding {len(truly_new):,} new rows...")

# ── Load model ────────────────────────────────────────────────────────────────
print("\nLoading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
model.encode(["warmup"])
print("Model ready.\n")

# ── Embed only new rows ───────────────────────────────────────────────────────
texts         = truly_new["_text"].tolist()[start_row:]
total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

for batch_num, i in enumerate(range(0, len(texts), BATCH_SIZE)):
    batch = texts[i: i + BATCH_SIZE]

    vecs = model.encode(
        batch,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype("float32")

    new_vectors.extend(vecs)

    rows_done = start_row + i + len(batch)
    pct       = rows_done / len(truly_new) * 100
    print(f"  Batch {batch_num+1}/{total_batches} — {rows_done:,}/{len(truly_new):,} new rows ({pct:.1f}%)", end="")

    # Save checkpoint every N batches
    if (batch_num + 1) % CHECKPOINT_EVERY == 0:
        np.save(CHECKPOINT, np.array(new_vectors, dtype=np.float32))
        print("  ✓ checkpoint saved", end="")

    print()

# ── Append new vectors to existing index ─────────────────────────────────────
print("\nAppending to existing index...")
new_vectors_arr = np.array(new_vectors, dtype=np.float32)

# Stack old + new vectors
combined_vectors = np.vstack([existing_vectors, new_vectors_arr])

# Stack old + new dataframe rows
combined_df = pd.concat([existing_df, truly_new], ignore_index=True)
combined_df = combined_df.drop_duplicates(subset=["entity_id"], keep="first")

# Save
np.save(VECTORS_PATH, combined_vectors)
combined_df.to_parquet(CLEAN_PATH, index=False)

# Clean up checkpoint
if os.path.exists(CHECKPOINT):
    os.remove(CHECKPOINT)

print(f"\n✅ Index updated successfully!")
print(f"   Was : {len(existing_df):,} rows")
print(f"   Added: {len(truly_new):,} new rows")
print(f"   Now : {len(combined_df):,} rows total")
print(f"\nRestart Streamlit to use the updated index.")