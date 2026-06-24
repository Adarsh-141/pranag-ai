# """
# Data Cleaner — Jay's Task 4

# Cleans the universal_index_final.parquet file before loading into ChromaDB.

# The Parquet has these columns:
#     entity_id, domain, name, description,
#     key_prop_1, key_prop_2, key_prop_3,
#     source, source_id, tags

# This module validates and cleans the file so vector_store.load_from_parquet()
# receives only well-formed data.

# Changes over GitHub version:
#     The original file was a single useless line:
#         def clean_data(data): return [d for d in data if d]

#     Replaced with a full clean_parquet() function that validates columns,
#     drops nulls, strips whitespace, normalises domain values, removes
#     duplicates, and removes descriptions too short to embed meaningfully.
#     The original clean_data() is kept for backward compatibility.
# """
# from __future__ import annotations

# import logging

# logger = logging.getLogger(__name__)

# REQUIRED_COLUMNS = {"entity_id", "domain", "name", "description"}

# VALID_DOMAINS = {
#     "biology", "chemistry", "physics", "materials", "environment", "general",
# }

# MIN_DESCRIPTION_LENGTH = 10


# def clean_parquet(path: str):
#     """
#     Load and clean universal_index_final.parquet for loading into ChromaDB.

#     Steps:
#       1. Validate required columns exist
#       2. Drop rows with null entity_id, name, or description
#       3. Strip whitespace from all string columns
#       4. Normalise domain to lowercase; replace unknown domains with 'biology'
#       5. Remove duplicate entity_ids (keep first)
#       6. Remove descriptions shorter than 10 characters

#     Args:
#         path: Path to the .parquet file

#     Returns:
#         Cleaned pandas DataFrame ready for vector_store.load_from_parquet()

#     Usage:
#         from search_engine.data_cleaner import clean_parquet
#         df = clean_parquet("universal_index_final.parquet")
#         df.to_parquet("universal_index_clean.parquet", index=False)
#     """
#     try:
#         import pandas as pd
#     except ImportError:
#         raise ImportError("pandas required: pip install pandas pyarrow")

#     import os
#     if not os.path.exists(path):
#         raise FileNotFoundError(f"Parquet file not found: {path}")

#     df = pd.read_parquet(path)
#     original = len(df)
#     logger.info("[data_cleaner] Loaded %d rows from %s", original, path)

#     # Step 1: validate required columns
#     missing_cols = REQUIRED_COLUMNS - set(df.columns)
#     if missing_cols:
#         raise ValueError(
#             f"Parquet missing required columns: {missing_cols}. "
#             f"Found: {list(df.columns)}"
#         )

#     # Step 2: drop nulls in key fields
#     df = df.dropna(subset=["entity_id", "description"])
#     df = df[df["description"].str.strip() != ""]

#     # Step 3: strip whitespace
#     for col in df.select_dtypes(include="object").columns:
#         df[col] = df[col].str.strip()

#     # Step 4: normalise domain
#     df["domain"] = df["domain"].str.lower().fillna("biology")
#     bad_domains = ~df["domain"].isin(VALID_DOMAINS)
#     if bad_domains.sum():
#         logger.warning(
#             "[data_cleaner] %d rows had unrecognised domain — set to 'biology'. Examples: %s",
#             bad_domains.sum(),
#             df.loc[bad_domains, "domain"].unique()[:5].tolist(),
#         )
#         df.loc[bad_domains, "domain"] = "biology"

#     # Step 5: remove duplicates
#     before = len(df)
#     df = df.drop_duplicates(subset=["entity_id"], keep="first")
#     if before - len(df):
#         logger.warning("[data_cleaner] Dropped %d duplicate entity_ids.", before - len(df))

#     # Step 6: remove too-short descriptions
#     before = len(df)
#     df = df[df["description"].str.len() >= MIN_DESCRIPTION_LENGTH]
#     if before - len(df):
#         logger.warning(
#             "[data_cleaner] Dropped %d rows with description < %d chars.",
#             before - len(df), MIN_DESCRIPTION_LENGTH
#         )

#     cleaned = len(df)
#     dropped = original - cleaned
#     logger.info(
#         "[data_cleaner] Done: %d rows kept, %d dropped (%.1f%%).",
#         cleaned, dropped, 100.0 * dropped / max(original, 1)
#     )
#     print(
#         f"[data_cleaner] {cleaned:,} entities ready "
#         f"({dropped:,} dropped from {original:,} original rows)."
#     )
#     return df


# def clean_data(data: list) -> list:
#     """
#     Simple list cleaner — kept for backward compatibility.
#     Removes None, empty strings, and whitespace-only entries.
#     """
#     return [d for d in data if d and str(d).strip()]


"""
Data Cleaner — Jay's Task 4

Cleans the universal_index_final.parquet file before loading into the vector store.

The Parquet has these columns:
    entity_id, domain, name, description,
    key_prop_1, key_prop_2, key_prop_3,
    source, source_id, tags

This module validates and cleans the file so vector_store.load_from_parquet()
receives only well-formed data.

Changes over GitHub version:
    The original file was a single useless line:
        def clean_data(data): return [d for d in data if d]

    Replaced with a full clean_parquet() function that validates columns,
    drops nulls, strips whitespace, normalises domain values, removes
    duplicates, and removes descriptions too short to embed meaningfully.
    The original clean_data() is kept for backward compatibility.

NOTE: clean_parquet() is optional — vector_store.load_from_parquet() does its
      own basic cleaning internally. Run clean_parquet() first when you want a
      saved pre-cleaned file to speed up repeated loads:

        from data_cleaner import clean_parquet
        df = clean_parquet("universal_index_final.parquet")
        df.to_parquet("universal_index_clean.parquet", index=False)
        # then point load_from_parquet() at the clean file
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"entity_id", "domain", "name", "description"}

VALID_DOMAINS = {
    "biology", "chemistry", "physics", "materials", "environment", "general",
}

MIN_DESCRIPTION_LENGTH = 10


def clean_parquet(path: str):
    """
    Load and clean universal_index_final.parquet.

    Steps:
      1. Validate required columns exist
      2. Drop rows with null entity_id or description
      3. Strip whitespace from all string columns
      4. Normalise domain to lowercase; replace unknown domains with 'biology'
      5. Remove duplicate entity_ids (keep first)
      6. Remove descriptions shorter than MIN_DESCRIPTION_LENGTH characters

    Args:
        path: Path to the .parquet file

    Returns:
        Cleaned pandas DataFrame ready for vector_store.load_from_parquet()

    Usage:
        from data_cleaner import clean_parquet
        df = clean_parquet("universal_index_final.parquet")
        df.to_parquet("universal_index_clean.parquet", index=False)
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required: pip install pandas pyarrow")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Parquet file not found: {path}")

    df = pd.read_parquet(path)
    original = len(df)
    logger.info("[data_cleaner] Loaded %d rows from %s", original, path)

    # Step 1: validate required columns
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Parquet missing required columns: {missing_cols}. "
            f"Found: {list(df.columns)}"
        )

    # Step 2: drop nulls in key fields
    df = df.dropna(subset=["entity_id", "description"])
    df = df[df["description"].str.strip() != ""]

    # Step 3: strip whitespace from all string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Step 4: normalise domain
    df["domain"] = df["domain"].str.lower().fillna("biology")
    bad_domains = ~df["domain"].isin(VALID_DOMAINS)
    if bad_domains.sum():
        logger.warning(
            "[data_cleaner] %d rows had unrecognised domain — set to 'biology'. Examples: %s",
            bad_domains.sum(),
            df.loc[bad_domains, "domain"].unique()[:5].tolist(),
        )
        df.loc[bad_domains, "domain"] = "biology"

    # Step 5: remove duplicates
    before = len(df)
    df = df.drop_duplicates(subset=["entity_id"], keep="first")
    if before - len(df):
        logger.warning("[data_cleaner] Dropped %d duplicate entity_ids.", before - len(df))

    # Step 6: remove too-short descriptions
    before = len(df)
    df = df[df["description"].str.len() >= MIN_DESCRIPTION_LENGTH]
    if before - len(df):
        logger.warning(
            "[data_cleaner] Dropped %d rows with description < %d chars.",
            before - len(df), MIN_DESCRIPTION_LENGTH
        )

    df = df.reset_index(drop=True)

    cleaned = len(df)
    dropped = original - cleaned
    logger.info(
        "[data_cleaner] Done: %d rows kept, %d dropped (%.1f%%).",
        cleaned, dropped, 100.0 * dropped / max(original, 1)
    )
    print(
        f"[data_cleaner] {cleaned:,} entities ready "
        f"({dropped:,} dropped from {original:,} original rows)."
    )
    return df


def clean_data(data: list) -> list:
    """
    Simple list cleaner — kept for backward compatibility.
    Removes None, empty strings, and whitespace-only entries.
    """
    return [d for d in data if d and str(d).strip()]