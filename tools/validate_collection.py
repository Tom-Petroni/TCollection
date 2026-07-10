"""Validate the core TCollection metadata files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT_DIR / "VERSION"
COLLECTION_CONFIG_PATH = ROOT_DIR / "config" / "collection.json"
NODE_REPOS_PATH = ROOT_DIR / "config" / "node_repos.json"
REGISTRY_PATH = ROOT_DIR / "nodes" / "registry.json"
CATALOG_PATH = ROOT_DIR / "nodes" / "catalog.json"
LOCK_PATH = ROOT_DIR / "config" / "node_lock.json"
MANIFEST_PATH = ROOT_DIR / "tcollection" / "manifest.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    collection = _read_json(COLLECTION_CONFIG_PATH)
    node_repos = _read_json(NODE_REPOS_PATH)
    registry = _read_json(REGISTRY_PATH)
    catalog = _read_json(CATALOG_PATH)
    lock = _read_json(LOCK_PATH)
    manifest = _read_json(MANIFEST_PATH)

    if collection.get("version") != version:
        raise SystemExit("VERSION and config/collection.json version do not match.")

    registry_nodes = registry.get("nodes", [])
    manifest_nodes = manifest.get("nodes", [])
    catalog_nodes = catalog.get("nodes", [])
    if len(registry_nodes) != len(manifest_nodes):
        raise SystemExit("nodes/registry.json and tcollection/manifest.json node counts differ.")
    if len(registry_nodes) != len(catalog_nodes):
        raise SystemExit("nodes/registry.json and nodes/catalog.json node counts differ.")

    registry_keys = set()
    mapping = node_repos.get("nodes", {})
    if not isinstance(mapping, dict):
        raise SystemExit("config/node_repos.json:nodes must be an object.")

    for entry in registry_nodes:
        key = str(entry.get("key", "")).strip()
        status = str(entry.get("status", "")).strip()
        bootstrap_module = str(entry.get("bootstrap_module", "")).strip()
        python_path = str(entry.get("python_path", "")).strip()
        if not key or not status or not bootstrap_module or not python_path:
            raise SystemExit(f"Registry entry is incomplete: {entry}")
        registry_keys.add(key)
        node_cfg = mapping.get(key, {})
        if isinstance(node_cfg, dict) and bool(node_cfg.get("enabled", True)):
            repo = str(node_cfg.get("repo", "")).strip()
            if not repo:
                raise SystemExit(f"Enabled node {key} has no repo configured in config/node_repos.json.")

    lock_keys = set()
    for entry in lock.get("nodes", []):
        key = str(entry.get("key", "")).strip()
        if key not in registry_keys:
            raise SystemExit(f"Lockfile references unknown node key: {key}")
        source = entry.get("source", {})
        if not isinstance(source, dict):
            raise SystemExit(f"Lockfile source is invalid for node: {key}")
        required_source_fields = [
            "provider",
            "repo",
            "repo_url",
            "releases_url",
            "tag",
            "asset_name",
            "archive_root",
        ]
        for field in required_source_fields:
            if not str(source.get(field, "")).strip():
                raise SystemExit(f"Lockfile source field '{field}' is missing for node: {key}")
        lock_keys.add(key)

    manifest_keys = set()
    for entry in manifest_nodes:
        key = str(entry.get("key", "")).strip()
        if key not in registry_keys:
            raise SystemExit(f"Manifest references unknown node key: {key}")
        source = entry.get("source")
        if key in lock_keys and not isinstance(source, dict):
            raise SystemExit(f"Manifest is missing source metadata for enabled node: {key}")
        manifest_keys.add(key)

    for entry in catalog_nodes:
        key = str(entry.get("key", "")).strip()
        if key not in registry_keys:
            raise SystemExit(f"Catalog references unknown node key: {key}")
        enabled_in_collection = bool(entry.get("enabled_in_collection", False))
        repo_url = str(entry.get("repo_url", "")).strip()
        if enabled_in_collection and not repo_url:
            raise SystemExit(f"Catalog is missing repo_url for enabled node: {key}")

    print("TCollection metadata validation passed.")


if __name__ == "__main__":
    main()
