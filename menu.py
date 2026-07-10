"""Nuke menu entrypoint for TCollection."""

import logging

from tcollection_bootstrap import load_runtime_callable

try:
    register_menu, _RUNTIME_ROOT = load_runtime_callable("tcollection.menu", "register_menu")
except Exception:
    register_menu = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

if callable(register_menu):
    try:
        register_menu()
    except Exception:
        logger.exception("TCollection failed to register its menu.")
