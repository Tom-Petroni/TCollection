"""Generate a human-facing node catalog from registry + lock metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _collection_utils import (
    NODE_LOCK_PATH,
    NODE_REPOS_PATH,
    REGISTRY_PATH,
    read_json,
    resolve_node_repo_ref,
    write_json,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
CATALOG_JSON_PATH = ROOT_DIR / "nodes" / "catalog.json"
CATALOG_DOC_PATH = ROOT_DIR / "docs" / "NODE_CATALOG_FR.md"


def _build_catalog(registry: dict[str, Any], node_repos: dict[str, Any], lock: dict[str, Any]) -> dict[str, Any]:
    lock_by_key = {
        str(entry.get("key", "")).strip(): entry
        for entry in lock.get("nodes", [])
        if isinstance(entry, dict)
    }

    out_nodes: list[dict[str, Any]] = []
    for entry in registry.get("nodes", []):
        if not isinstance(entry, dict):
            continue

        key = str(entry.get("key", "")).strip()
        lock_entry = lock_by_key.get(key, {})
        source = lock_entry.get("source", {}) if isinstance(lock_entry, dict) else {}
        repo_ref = resolve_node_repo_ref(node_repos, key, str(entry.get("version", "")).strip())

        repo = str(source.get("repo", repo_ref.get("repo", ""))).strip()
        repo_url = str(source.get("repo_url", repo_ref.get("repo_url", ""))).strip()
        releases_url = str(source.get("releases_url", repo_ref.get("releases_url", ""))).strip()
        enabled_in_collection = key in lock_by_key

        out_nodes.append(
            {
                "key": key,
                "label": str(entry.get("label", key)).strip() or key,
                "version": str(entry.get("version", "")).strip(),
                "status": str(entry.get("status", "")).strip(),
                "enabled_in_collection": enabled_in_collection,
                "repo": repo,
                "repo_url": repo_url,
                "releases_url": releases_url,
                "tag": str(source.get("tag", "")).strip(),
                "asset_name": str(source.get("asset_name", "")).strip(),
                "notes": str(entry.get("notes", "")).strip(),
            }
        )

    out_nodes.sort(key=lambda item: item["key"])
    return {
        "schema_version": "1.0",
        "updated_at": registry.get("updated_at", ""),
        "nodes": out_nodes,
    }


def _render_markdown(catalog: dict[str, Any]) -> str:
    active_nodes = [node for node in catalog.get("nodes", []) if node.get("enabled_in_collection")]
    planned_nodes = [node for node in catalog.get("nodes", []) if not node.get("enabled_in_collection")]

    lines = [
        "# TCollection: catalogue des nodes",
        "",
        "Ce document est genere depuis `nodes/registry.json`, `config/node_repos.json`",
        "et `config/node_lock.json`.",
        "",
        "## Nodes actifs dans la collection",
        "",
        "| Node | Version | Status | Repo | Releases | Asset |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for node in active_nodes:
        repo_cell = f"[{node['repo']}]({node['repo_url']})" if node.get("repo_url") else node.get("repo", "")
        releases_cell = (
            f"[releases]({node['releases_url']})" if node.get("releases_url") else ""
        )
        lines.append(
            "| {label} | {version} | {status} | {repo} | {releases} | `{asset}` |".format(
                label=node["label"],
                version=node["version"] or "-",
                status=node["status"] or "-",
                repo=repo_cell or "-",
                releases=releases_cell or "-",
                asset=node["asset_name"] or "-",
            )
        )

    lines.extend(
        [
            "",
            "## Nodes suivis mais pas encore embarques",
            "",
            "| Node | Version | Status | Repo cible | Notes |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for node in planned_nodes:
        repo_cell = f"[{node['repo']}]({node['repo_url']})" if node.get("repo_url") else f"`{node['repo']}`"
        lines.append(
            "| {label} | {version} | {status} | {repo} | {notes} |".format(
                label=node["label"],
                version=node["version"] or "-",
                status=node["status"] or "-",
                repo=repo_cell if node.get("repo") else "-",
                notes=node["notes"] or "-",
            )
        )

    lines.extend(
        [
            "",
            "## Mise a jour rapide d'un node",
            "",
            "Exemple avec `TNoise`:",
            "",
            "```powershell",
            "python tools/promote_node.py TNoise",
            "python tools/sync_node_lock.py",
            "python tools/sync_manifest.py",
            "python tools/sync_node_catalog.py",
            "python tools/audit_node_sources.py --strict-enabled",
            "python tools/validate_collection.py",
            "python tools/assemble_collection.py --source github-release --statuses stable",
            "```",
            "",
            "Un audit GitHub plus complet peut etre genere avec",
            "`python tools/audit_node_sources.py --strict-enabled`.",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    registry = read_json(REGISTRY_PATH)
    node_repos = read_json(NODE_REPOS_PATH)
    lock = read_json(NODE_LOCK_PATH)
    catalog = _build_catalog(registry, node_repos, lock)

    write_json(CATALOG_JSON_PATH, catalog)
    CATALOG_DOC_PATH.write_text(_render_markdown(catalog) + "\n", encoding="utf-8")
    print(f"Synced {CATALOG_JSON_PATH} and {CATALOG_DOC_PATH}")


if __name__ == "__main__":
    main()
