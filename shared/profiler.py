import time
import logging
from contextlib import contextmanager
from streamlit.logger import get_logger

logger = get_logger(__name__)

@contextmanager
def time_block(block_name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"⏱️ [PROFILE] {block_name} took {elapsed:.2f}ms")