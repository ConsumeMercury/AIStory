"""
Central debug switches for AIStory.

Set in .env or the OS environment, then restart the server / CLI.

  AISTORY_DEBUG=1          — verbose logging + /api/debug/* endpoints
  AISTORY_DEBUG_TOKENS=1   — print Gemini prompt token estimates (narrator)
  AISTORY_HINTS=plain      — action hint verbosity (see action_hints.py)
"""

import logging
import os

_CONFIGURED = False


def _truthy(name, default=False):
    raw = os.environ.get(name, "")
    if not raw and default:
        return True
    return raw.strip().lower() in ("1", "true", "yes", "on")


def debug_enabled():
    return _truthy("AISTORY_DEBUG")


def debug_tokens():
    return _truthy("AISTORY_DEBUG_TOKENS")


def setup_logging(force=False):
    """Configure root logger once. DEBUG level when AISTORY_DEBUG=1."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return
    level = logging.DEBUG if debug_enabled() else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    _CONFIGURED = True


def log_debug(logger, msg, *args, **kwargs):
    if debug_enabled():
        logger.debug(msg, *args, **kwargs)
