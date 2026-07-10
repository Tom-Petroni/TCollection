"""Shared helpers for TCollection tooling."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
COLLECTION_CONFIG_PATH = ROOT_DIR / "config" / "collection.json"
DEV_SOURCES_PATH = ROOT_DIR / "config" / "dev_sources.json"
NODE_REPOS_PATH = ROOT_DIR / "config" / "node_repos.json"
NODE_LOCK_PATH = ROOT_DIR / "config" / "node_lock.json"
REGISTRY_PATH = ROOT_DIR / "nodes" / "registry.json"
MANIFEST_PATH = ROOT_DIR / "tcollection" / "manifest.json"
VERSION_PATH = ROOT_DIR / "VERSION"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_version() -> str:
    return VERSION_PATH.read_text(encoding="utf-8").strip()


def resolve_repo_path(node_key: str, repo_path: str = "") -> Path:
    if repo_path.strip():
        candidate = Path(repo_path)
        return candidate if candidate.is_absolute() else (ROOT_DIR / candidate).resolve()

    dev_sources = read_json(DEV_SOURCES_PATH)
    nodes = dev_sources.get("nodes", {})
    if isinstance(nodes, dict):
        node_cfg = nodes.get(node_key, {})
        if isinstance(node_cfg, dict):
            explicit = str(node_cfg.get("repo_path", "")).strip()
            if explicit:
                return (ROOT_DIR / explicit).resolve()

    pattern = str(dev_sources.get("default_repo_path_pattern", "{key}"))
    workspace_root = str(dev_sources.get("workspace_root", "..")).strip()
    relative = pattern.format(key=node_key)
    return (ROOT_DIR / workspace_root / relative).resolve()


def prune_pycache(root: Path) -> None:
    for path in root.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path)

    for path in root.rglob("*.pyc"):
        if path.is_file():
            path.unlink()


def normalize_version_tuple(version: str) -> tuple[int, ...]:
    cleaned = version.strip().lower().removeprefix("v")
    parts: list[int] = []
    for token in cleaned.split("."):
        try:
            parts.append(int(token))
        except ValueError:
            break
    return tuple(parts)
