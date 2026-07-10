"""Sync the runtime manifest from collection config and nodes registry."""

from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
COLLECTION_CONFIG_PATH = ROOT_DIR / "config" / "collection.json"
REGISTRY_PATH = ROOT_DIR / "nodes" / "registry.json"
MANIFEST_PATH = ROOT_DIR / "tcollection" / "manifest.json"


def main() -> None:
    collection = json.loads(COLLECTION_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))

    manifest = {
        "collection": {
            "key": collection.get("key", "TCollection"),
            "display_name": collection.get("display_name", "TCollection"),
            "version": collection.get("version", "0.0.0"),
            "status": collection.get("status", "unknown"),
        },
        "nodes": registry.get("nodes", []),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Synced {MANIFEST_PATH} from {COLLECTION_CONFIG_PATH} and {REGISTRY_PATH}")


if __name__ == "__main__":
    main()

