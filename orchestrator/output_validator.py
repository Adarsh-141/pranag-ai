"""
Output Validator

Validates the raw spec dict against the Pydantic Spec model.
Returns the serialised dict on success, or raises ValueError with details on failure.
"""
import logging
from pydantic import ValidationError
from shared.models import Spec

logger = logging.getLogger(__name__)


def validate_spec(data: dict) -> dict | None:
    """
    Validate *data* against the Spec schema.

    Returns:
        The validated dict (via model_dump) if valid.
        None if validation fails (caller should count as a retry).
    """
    if not data:
        logger.warning("[output_validator] Received empty data.")
        return None

    try:
        spec = Spec(**data)
        return spec.model_dump()
    except ValidationError as exc:
        logger.warning(
            "[output_validator] Spec validation failed:\n%s",
            exc.json(indent=2),
        )
        return None
