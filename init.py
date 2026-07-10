"""Nuke entrypoint for TCollection."""

import logging

try:
    from tcollection.loader import bootstrap_status
    from tcollection.updater import notify_startup_update
except Exception:
    bootstrap_status = None  # type: ignore[assignment]
    notify_startup_update = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

if callable(bootstrap_status):
    try:
        bootstrap_status("stable")
    except Exception:
        logger.exception("TCollection failed to bootstrap stable nodes.")

if callable(notify_startup_update):
    try:
        notify_startup_update(background=True)
    except Exception:
        logger.exception("TCollection failed to check for startup updates.")

