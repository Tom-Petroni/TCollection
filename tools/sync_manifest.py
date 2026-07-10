"""Sync the runtime manifest from collection config and nodes registry."""

from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
COLLECTION_CONFIG_PATH = ROOT_DIR / "config" / "collection.json"
REGISTRY_PATH = ROOT_DIR / "nodes" / "registry.json"
LOCK_PATH = ROOT_DIR / "config" / "node_lock.json"
MANIFEST_PATH = ROOT_DIR / "tcollection" / "manifest.json"


def main() -> None:
    collection = json.loads(COLLECTION_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8-sig"))
    lock_by_key = {
        str(entry.get("key", "")).strip(): entry
        for entry in lock.get("nodes", [])
        if isinstance(entry, dict)
    }

    manifest_nodes = []
    for entry in registry.get("nodes", []):
        if not isinstance(entry, dict):
            continue
        node_entry = dict(entry)
        key = str(node_entry.get("key", "")).strip()
        source_entry = lock_by_key.get(key, {}).get("source")
        if isinstance(source_entry, dict):
            node_entry["source"] = source_entry
        manifest_nodes.append(node_entry)

    manifest = {
        "collection": {
            "key": collection.get("key", "TCollection"),
            "display_name": collection.get("display_name", "TCollection"),
            "version": collection.get("version", "0.0.0"),
            "status": collection.get("status", "unknown"),
            "links": collection.get("links", {}),
        },
        "nodes": manifest_nodes,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Synced {MANIFEST_PATH} from {COLLECTION_CONFIG_PATH} and {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
