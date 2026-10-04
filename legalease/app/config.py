"""Central configuration (environment-driven)."""
import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("LEGALEASE_MODEL", "claude-sonnet-5-5")
AI_TIMEOUT_SECONDS = int(os.getenv("LEGALEASE_AI_TIMEOUT", "90"))

MAX_FIELD_LEN = 2000            # max characters per user-supplied field
MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = 4 * 1024 * 1024
RATE_LIMIT_PER_MIN = int(os.getenv("LEGALEASE_RATE_LIMIT", "30"))

DISCLAIMER = (
    "This document was generated automatically from a template and the information "
    "you supplied. It is not legal advice. Laws vary by jurisdiction; have a qualified "
    "lawyer review it before you sign."
)
