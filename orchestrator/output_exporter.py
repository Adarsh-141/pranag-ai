"""
Output Exporter

Saves the validated spec to disk as spec.json and optionally
POSTs it to Srikar's simulation endpoint.
"""
import json
import logging
import os
from datetime import datetime, timezone

import requests

from shared.config import settings

logger = logging.getLogger(__name__)


def export_spec(spec: dict, pipeline_id: str) -> str | None:
    """
    Save spec to disk and optionally POST to the simulation endpoint.

    Args:
        spec:        The validated spec dict from output_validator.
        pipeline_id: UUID string for this run (used in the filename).

    Returns:
        The file path where the spec was saved, or None if export was disabled.
    """
    filepath = None

    # ── 1. Save to disk ───────────────────────────────────────────────────────
    if settings.export_to_file:
        os.makedirs(settings.output_dir, exist_ok=True)
        filename = "spec.json"
        filepath = os.path.join(settings.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)

        logger.info("[output_exporter] Spec saved → %s", filepath)

    # ── 2. POST to Srikar's endpoint (if configured) ──────────────────────────
    if settings.srikar_endpoint:
        try:
            resp = requests.post(
                settings.srikar_endpoint,
                json={"pipeline_id": pipeline_id, "spec": spec},
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            logger.info(
                "[output_exporter] Spec delivered to simulation endpoint. "
                "Status: %d", resp.status_code
            )
        except requests.exceptions.ConnectionError:
            logger.warning(
                "[output_exporter] Simulation endpoint not reachable (%s). "
                "Spec saved to disk only.", settings.srikar_endpoint
            )
        except requests.exceptions.Timeout:
            logger.warning("[output_exporter] Simulation endpoint timed out.")
        except requests.exceptions.HTTPError as exc:
            logger.warning("[output_exporter] Simulation endpoint error: %s", exc)

    return filepath
