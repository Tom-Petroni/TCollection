"""Validate the core TCollection metadata files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT_DIR / "VERSION"
COLLECTION_CONFIG_PATH = ROOT_DIR / "config" / "collection.json"
REGISTRY_PATH = ROOT_DIR / "nodes" / "registry.json"
LOCK_PATH = ROOT_DIR / "config" / "node_lock.json"
MANIFEST_PATH = ROOT_DIR / "tcollection" / "manifest.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    collection = _read_json(COLLECTION_CONFIG_PATH)
    registry = _read_json(REGISTRY_PATH)
    lock = _read_json(LOCK_PATH)
    manifest = _read_json(MANIFEST_PATH)

    if collection.get("version") != version:
        raise SystemExit("VERSION and config/collection.json version do not match.")

    registry_nodes = registry.get("nodes", [])
    manifest_nodes = manifest.get("nodes", [])
    if len(registry_nodes) != len(manifest_nodes):
        raise SystemExit("nodes/registry.json and tcollection/manifest.json node counts differ.")

    registry_keys = set()
    for entry in registry_nodes:
        key = str(entry.get("key", "")).strip()
        status = str(entry.get("status", "")).strip()
        bootstrap_module = str(entry.get("bootstrap_module", "")).strip()
        python_path = str(entry.get("python_path", "")).strip()
        if not key or not status or not bootstrap_module or not python_path:
            raise SystemExit(f"Registry entry is incomplete: {entry}")
        registry_keys.add(key)

    for entry in lock.get("nodes", []):
        key = str(entry.get("key", "")).strip()
        if key not in registry_keys:
            raise SystemExit(f"Lockfile references unknown node key: {key}")

    print("TCollection metadata validation passed.")


if __name__ == "__main__":
    main()

