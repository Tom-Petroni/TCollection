"""Generate node lockfile from registry + repo mapping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT_DIR / "nodes" / "registry.json"
NODE_REPOS_PATH = ROOT_DIR / "config" / "node_repos.json"
OUTPUT_PATH = ROOT_DIR / "config" / "node_lock.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _format_pattern(pattern: str, key: str, version: str, repo: str) -> str:
    owner, _, name = repo.partition("/")
    return pattern.format(
        key=key,
        version=version,
        owner=owner,
        repo=name or repo,
        repo_full=repo,
    )


def _build_lock(registry: dict[str, Any], node_repos: dict[str, Any]) -> dict[str, Any]:
    defaults = node_repos.get("defaults", {})
    repo_name_pattern = str(node_repos.get("repo_name_pattern", "{key}"))
    owner = str(node_repos.get("owner", "")).strip()

    default_tag_pattern = str(defaults.get("tag_pattern", "v{version}"))
    default_asset_pattern = str(defaults.get("asset_name_pattern", "{key}-v{version}.zip"))
    default_archive_pattern = str(defaults.get("archive_root_pattern", "{key}-{version}"))
    default_repo_url_pattern = str(defaults.get("repo_url_pattern", "https://github.com/{repo_full}"))
    default_releases_url_pattern = str(
        defaults.get("releases_url_pattern", "https://github.com/{repo_full}/releases")
    )

    mapping = node_repos.get("nodes", {})
    if not isinstance(mapping, dict):
        raise ValueError("config/node_repos.json:nodes must be an object")

    out_nodes: list[dict[str, Any]] = []
    for entry in registry.get("nodes", []):
        if not isinstance(entry, dict):
            continue

        key = str(entry.get("key", "")).strip()
        version = str(entry.get("version", "")).strip()
        status = str(entry.get("status", "")).strip()
        if not key or not version:
            continue

        node_cfg_raw = mapping.get(key, {})
        node_cfg = node_cfg_raw if isinstance(node_cfg_raw, dict) else {}
        if not bool(node_cfg.get("enabled", True)):
            continue

        repo = str(node_cfg.get("repo", "")).strip()
        if not repo:
            repo_name = _format_pattern(repo_name_pattern, key=key, version=version, repo="")
            repo = f"{owner}/{repo_name}" if owner else repo_name

        tag_pattern = str(node_cfg.get("tag_pattern", default_tag_pattern))
        asset_pattern = str(node_cfg.get("asset_name_pattern", default_asset_pattern))
        archive_pattern = str(node_cfg.get("archive_root_pattern", default_archive_pattern))
        repo_url_pattern = str(node_cfg.get("repo_url_pattern", default_repo_url_pattern))
        releases_url_pattern = str(node_cfg.get("releases_url_pattern", default_releases_url_pattern))

        tag = _format_pattern(tag_pattern, key=key, version=version, repo=repo)
        asset_name = _format_pattern(asset_pattern, key=key, version=version, repo=repo)
        archive_root = _format_pattern(archive_pattern, key=key, version=version, repo=repo)
        repo_url = _format_pattern(repo_url_pattern, key=key, version=version, repo=repo)
        releases_url = _format_pattern(releases_url_pattern, key=key, version=version, repo=repo)

        out_nodes.append(
            {
                "key": key,
                "version": version,
                "status": status,
                "label": str(entry.get("label", "")).strip(),
                "source": {
                    "provider": str(
                        node_cfg.get("provider", node_repos.get("default_provider", "github-release"))
                    ),
                    "repo": repo,
                    "repo_url": repo_url,
                    "releases_url": releases_url,
                    "tag": tag,
                    "asset_name": asset_name,
                    "archive_root": archive_root,
                },
            }
        )

    out_nodes.sort(key=lambda item: item["key"])
    return {
        "schema_version": "1.0",
        "registry_updated_at": registry.get("updated_at", ""),
        "nodes": out_nodes,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sync node lock from registry + repo mapping.")
    parser.add_argument("--registry", default=str(REGISTRY_PATH))
    parser.add_argument("--node-repos", default=str(NODE_REPOS_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args(argv)

    registry_path = Path(args.registry).resolve()
    node_repos_path = Path(args.node_repos).resolve()
    output_path = Path(args.output).resolve()

    registry = _read_json(registry_path)
    node_repos = _read_json(node_repos_path)
    lock = _build_lock(registry, node_repos)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote node lock: {output_path}")


if __name__ == "__main__":
    main()
