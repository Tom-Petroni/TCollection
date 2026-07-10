"""Promote a sibling node repo version into TCollection metadata."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from _collection_utils import REGISTRY_PATH, read_json, resolve_repo_path, write_json
from sync_node_catalog import main as sync_node_catalog_main
from sync_manifest import main as sync_manifest_main
from sync_node_lock import main as sync_node_lock_main
from validate_collection import main as validate_collection_main


def _load_node_repo_metadata(repo_path: Path) -> dict[str, Any]:
    node_json_path = repo_path / "node.json"
    if not node_json_path.is_file():
        raise FileNotFoundError(f"Missing node.json in {repo_path}")
    return read_json(node_json_path)


def _runtime_python_path(node_key: str) -> str:
    return f"nodes/{node_key}/publish"


def _build_registry_entry(
    node_key: str,
    repo_metadata: dict[str, Any],
    status_override: str,
) -> dict[str, Any]:
    status = status_override.strip() or str(repo_metadata.get("status", "stable")).strip() or "stable"
    return {
        "key": str(repo_metadata.get("key", node_key)).strip() or node_key,
        "label": str(repo_metadata.get("label", node_key)).strip() or node_key,
        "version": str(repo_metadata.get("version", "")).strip(),
        "status": status,
        "class_name": str(repo_metadata.get("class_name", "")).strip(),
        "bootstrap_module": str(repo_metadata.get("bootstrap_module", "")).strip(),
        "python_path": _runtime_python_path(node_key),
        "notes": str(repo_metadata.get("notes", "")).strip(),
    }


def _upsert_registry_entry(registry: dict[str, Any], entry: dict[str, Any]) -> None:
    nodes = registry.setdefault("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("nodes/registry.json:nodes must be a list")

    key = entry["key"]
    for index, current in enumerate(nodes):
        if isinstance(current, dict) and str(current.get("key", "")).strip() == key:
            nodes[index] = entry
            return

    nodes.append(entry)


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote a node repo version into TCollection.")
    parser.add_argument("node_key", help="Node key to promote, for example TNoise")
    parser.add_argument("--repo-path", default="", help="Override the sibling repo path.")
    parser.add_argument("--status", default="", help="Optional status override in the collection registry.")
    args = parser.parse_args()

    node_key = args.node_key.strip()
    repo_path = resolve_repo_path(node_key, args.repo_path)
    repo_metadata = _load_node_repo_metadata(repo_path)

    entry = _build_registry_entry(node_key, repo_metadata, args.status)
    if not entry["version"]:
        raise SystemExit(f"Node repo {repo_path} has no version in node.json")

    registry = read_json(REGISTRY_PATH)
    registry["updated_at"] = date.today().isoformat()
    _upsert_registry_entry(registry, entry)
    registry_nodes = registry.get("nodes", [])
    if isinstance(registry_nodes, list):
        registry_nodes.sort(key=lambda item: str(item.get("key", "")).strip())
    write_json(REGISTRY_PATH, registry)

    sync_node_lock_main([])
    sync_manifest_main()
    sync_node_catalog_main()
    validate_collection_main()
    print(f"Promoted {node_key} from {repo_path}")


if __name__ == "__main__":
    main()
