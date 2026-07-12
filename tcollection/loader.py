"""Runtime loader for TCollection node modules."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import nuke  # ty: ignore[unresolved-import]

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"

_BOOTSTRAPPED: set[str] = set()
_MANIFEST_CACHE: dict[str, Any] | None = None


def _normalized(path: str) -> str:
    return path.replace(os.sep, "/")


def _load_manifest() -> dict[str, Any]:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        _MANIFEST_CACHE = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return _MANIFEST_CACHE


def get_collection_info() -> dict[str, Any]:
    return dict(_load_manifest().get("collection", {}))


def get_nodes() -> list[dict[str, Any]]:
    data = _load_manifest()
    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        return []
    return [entry for entry in nodes if isinstance(entry, dict)]


def get_nodes_by_status(status: str) -> list[dict[str, Any]]:
    return [entry for entry in get_nodes() if entry.get("status") == status]


def get_node(node_key: str) -> dict[str, Any] | None:
    for entry in get_nodes():
        if entry.get("key") == node_key:
            return entry
    return None


def _resolve_python_path(entry: dict[str, Any]) -> Path:
    rel_path = str(entry.get("python_path", "")).strip()
    return (ROOT_DIR / rel_path).resolve()


def _icon_candidates(entry: dict[str, Any]) -> list[Path]:
    python_path = _resolve_python_path(entry)
    key = str(entry.get("key", "")).strip()
    label = str(entry.get("label", key)).strip() or key
    class_name = str(entry.get("class_name", "")).strip()

    names: list[str] = []
    for candidate in (key, label, class_name):
        if candidate and candidate not in names:
            names.append(candidate)

    candidates: list[Path] = []
    for name in names:
        candidates.append(python_path / key / "resources" / f"{name}.png")
        candidates.append(python_path / "resources" / f"{name}.png")
    return candidates


def resolve_node_icon_path(node_key: str) -> str:
    entry = get_node(node_key)
    if entry is None:
        return ""

    for candidate in _icon_candidates(entry):
        if candidate.is_file():
            return _normalized(str(candidate))
    return ""


def _ensure_python_path(path: Path) -> None:
    norm = _normalized(str(path))
    for existing in sys.path:
        if _normalized(existing) == norm:
            return
    sys.path.insert(0, str(path))


def ensure_node_python_path(node_key: str) -> bool:
    entry = get_node(node_key)
    if entry is None:
        nuke.tprint(f"[TCollection] Unknown node key: {node_key}")
        return False

    python_path = _resolve_python_path(entry)
    if not python_path.exists():
        nuke.tprint(f"[TCollection] Missing path for {node_key}: {python_path}")
        return False

    _ensure_python_path(python_path)
    return True


def bootstrap_node(node_key: str) -> bool:
    entry = get_node(node_key)
    if entry is None:
        nuke.tprint(f"[TCollection] Unknown node key: {node_key}")
        return False

    if node_key in _BOOTSTRAPPED:
        return True

    python_path = _resolve_python_path(entry)
    if not python_path.exists():
        nuke.tprint(f"[TCollection] Missing path for {node_key}: {python_path}")
        return False

    _ensure_python_path(python_path)

    module_name = str(entry.get("bootstrap_module", "")).strip()
    if not module_name:
        nuke.tprint(f"[TCollection] Missing bootstrap module for {node_key}")
        return False

    try:
        importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - Nuke runtime dependency
        nuke.tprint(f"[TCollection] Failed bootstrap {node_key} ({module_name}): {exc}")
        return False

    _BOOTSTRAPPED.add(node_key)
    return True


def bootstrap_status(status: str) -> None:
    for entry in get_nodes_by_status(status):
        node_key = str(entry.get("key", "")).strip()
        if node_key:
            bootstrap_node(node_key)
