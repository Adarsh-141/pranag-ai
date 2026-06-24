"""
run_once.py — Pre-compute embeddings for universal_index_final.parquet

Run once from your Prompt_Parser folder:
    python run_once.py

Supports resume — if interrupted, run again and it picks up where it left off.
Saves a checkpoint every 50 batches so you never lose more than ~50 batches of work.
"""
import os
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# ── Path config ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARQUET_PATH = os.path.normpath(os.path.join(
    BASE_DIR, "..", "PINN Framework", "datasrc", "universal_index_final.parquet"
))

base         = PARQUET_PATH.replace(".parquet", "")
VECTORS_PATH = base + ".vectors.npy"
CLEAN_PATH   = base + ".clean.parquet"
CHECKPOINT   = base + ".checkpoint.npy"   # partial progress saved here

BATCH_SIZE       = 512
CHECKPOINT_EVERY = 50   # save to disk every 50 batches

# ── Load + clean parquet ──────────────────────────────────────────────────────
print(f"Loading parquet from:\n  {PARQUET_PATH}\n")
df = pd.read_parquet(PARQUET_PATH)

df["_text"] = (
    df["name"].fillna("").str.strip()
    + ". "
    + df["description"].fillna("").str.strip()
)
df = df[df["_text"].str.len() >= 10].reset_index(drop=True)
texts = df["_text"].tolist()
total = len(texts)
print(f"Total rows to embed: {total:,}")

# ── Check if already fully done ───────────────────────────────────────────────
if os.path.exists(VECTORS_PATH) and os.path.exists(CLEAN_PATH):
    existing = np.load(VECTORS_PATH)
    if len(existing) == total:
        print("\n✅ Already complete! Nothing to do.")
        print(f"   {VECTORS_PATH}")
        print(f"   {CLEAN_PATH}")
        print("\nApp startup will take ~1 second.")
        exit(0)

# ── Load checkpoint if exists (resume support) ────────────────────────────────
if os.path.exists(CHECKPOINT):
    partial = np.load(CHECKPOINT)
    start_row = len(partial)
    print(f"\n⚡ Resuming from row {start_row:,} / {total:,} ({start_row/total*100:.1f}% already done)")
    all_vectors = list(partial)   # convert to list so we can append
else:
    start_row = 0
    all_vectors = []
    print("\nStarting fresh embedding run...")

# ── Load model ────────────────────────────────────────────────────────────────
print("\nLoading embedding model...")
model = SentenceTransformer("paraphrase-MiniLM-L3-v2")
model.encode(["warmup"])   # pre-warm PyTorch kernels
print("Model ready.\n")

# ── Embed in batches with checkpointing ───────────────────────────────────────
remaining_texts = texts[start_row:]
total_batches   = (len(remaining_texts) + BATCH_SIZE - 1) // BATCH_SIZE

print(f"Embedding {len(remaining_texts):,} remaining rows in batches of {BATCH_SIZE}...")
print(f"Checkpoint saved every {CHECKPOINT_EVERY} batches (~{CHECKPOINT_EVERY * BATCH_SIZE:,} rows)\n")

for batch_num, i in enumerate(range(0, len(remaining_texts), BATCH_SIZE)):
    batch = remaining_texts[i: i + BATCH_SIZE]

    vecs = model.encode(
        batch,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype("float32")

    all_vectors.extend(vecs)

    rows_done  = start_row + i + len(batch)
    pct        = rows_done / total * 100
    batches_left = total_batches - batch_num - 1

    print(f"  Batch {batch_num+1}/{total_batches} — {rows_done:,}/{total:,} rows ({pct:.1f}%)", end="")

    # Save checkpoint every N batches
    if (batch_num + 1) % CHECKPOINT_EVERY == 0:
        np.save(CHECKPOINT, np.array(all_vectors, dtype=np.float32))
        print(f"  ✓ checkpoint saved", end="")

    print()

# ── Save final output files ───────────────────────────────────────────────────
print("\nSaving final files...")
vectors = np.array(all_vectors, dtype=np.float32)
np.save(VECTORS_PATH, vectors)
df.to_parquet(CLEAN_PATH, index=False)

# Clean up checkpoint file — no longer needed
if os.path.exists(CHECKPOINT):
    os.remove(CHECKPOINT)
    print("Checkpoint file removed.")

print(f"\n✅ Done! Saved:")
print(f"   {VECTORS_PATH}")
print(f"   {CLEAN_PATH}")
print(f"\n{total:,} entities embedded and cached.")
print("App startup will now take ~1 second every time — including after PC restarts.")