"""Nuke menu entrypoint for TCollection."""

import logging

try:
    from tcollection.menu import register_menu
except Exception:
    register_menu = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

if callable(register_menu):
    try:
        register_menu()
    except Exception:
        logger.exception("TCollection failed to register its menu.")

