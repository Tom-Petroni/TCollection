"""Menu registration for TCollection."""

from __future__ import annotations

from typing import Any

import nuke  # ty: ignore[unresolved-import]

from .loader import bootstrap_node, get_collection_info, get_node, get_nodes_by_status
from .updater import check_for_updates

_MENU_REGISTERED = False
_MENU_NAME = "TCollection"


def _create_node(node_key: str) -> None:
    entry = get_node(node_key)
    if entry is None:
        nuke.tprint(f"[TCollection] Unknown node key: {node_key}")
        return

    class_name = str(entry.get("class_name", "")).strip()
    if not class_name:
        nuke.tprint(f"[TCollection] Node '{node_key}' has no class_name.")
        return

    if not bootstrap_node(node_key):
        nuke.message(f"TCollection: impossible de charger '{node_key}'.")  # ty: ignore[unresolved-attribute]
        return

    try:
        nuke.createNode(class_name)
    except Exception as exc:
        nuke.message(f"TCollection: echec createNode('{class_name}'):\n{exc}")  # ty: ignore[unresolved-attribute]


def _command_for(node_key: str) -> str:
    return f"import tcollection.menu as _tm; _tm._create_node('{node_key}')"


def _add_node_entries(menu_obj: Any, status: str) -> None:
    for entry in get_nodes_by_status(status):
        node_key = str(entry.get("key", "")).strip()
        label = str(entry.get("label", node_key)).strip() or node_key
        class_name = str(entry.get("class_name", "")).strip()
        if not node_key or not class_name:
            continue
        menu_obj.addCommand(label, _command_for(node_key))


def _show_about() -> None:
    info = get_collection_info()
    message = (
        f"TCollection\n\n"
        f"Version: {info.get('version', 'unknown')}\n"
        f"Status: {info.get('status', 'unknown')}\n"
        f"Nodes stable/test/hold drives the runtime menu and loading policy."
    )
    nuke.message(message)  # ty: ignore[unresolved-attribute]


def _check_for_updates_ui() -> None:
    result = check_for_updates()
    if result["available"]:
        nuke.message(  # ty: ignore[unresolved-attribute]
            "A newer TCollection version is available.\n\n"
            f"Current: {result['current_version']}\n"
            f"Latest: {result['latest_version']}\n"
            f"Channel: {result['channel']}\n"
        )
        return

    reason = result.get("reason", "No update available.")
    nuke.message(f"TCollection update check:\n\n{reason}")  # ty: ignore[unresolved-attribute]


def register_menu() -> None:
    global _MENU_REGISTERED

    toolbar = nuke.toolbar("Nodes")
    if toolbar is None:
        toolbar = nuke.menu("Nodes")
    menu_obj = toolbar.findItem(_MENU_NAME)

    if _MENU_REGISTERED and menu_obj is not None:
        return
    if _MENU_REGISTERED and menu_obj is None:
        _MENU_REGISTERED = False

    if menu_obj is not None:
        try:
            toolbar.removeItem(_MENU_NAME)
        except Exception:
            pass

    menu_obj = toolbar.addMenu(_MENU_NAME)
    _add_node_entries(menu_obj, "stable")
    _add_node_entries(menu_obj, "test")
    menu_obj.addSeparator()
    menu_obj.addCommand("Check For Updates...", "import tcollection.menu as _tm; _tm._check_for_updates_ui()")
    menu_obj.addCommand("About TCollection", "import tcollection.menu as _tm; _tm._show_about()")
    _MENU_REGISTERED = True

