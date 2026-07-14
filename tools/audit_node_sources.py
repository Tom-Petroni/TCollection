"""Audit GitHub repository and release availability for node sources."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from _collection_utils import NODE_LOCK_PATH, NODE_REPOS_PATH, REGISTRY_PATH, read_json, resolve_node_repo_ref

ROOT_DIR = Path(__file__).resolve().parents[1]
AUDIT_JSON_PATH = ROOT_DIR / "audit" / "node_source_audit.json"
AUDIT_DOC_PATH = ROOT_DIR / "audit" / "NODE_SOURCE_AUDIT_FR.md"


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "TCollection-Node-Source-Audit",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GH_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_json(url: str) -> tuple[int, dict[str, Any]]:
    request = Request(url, headers=_github_headers())
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload) if payload else {}
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            data = {"message": payload.strip()}
        return exc.code, data
    except URLError as exc:
        return 0, {"message": str(exc.reason)}


def _audit_node(entry: dict[str, Any], node_repos: dict[str, Any], lock_by_key: dict[str, Any]) -> dict[str, Any]:
    key = str(entry.get("key", "")).strip()
    version = str(entry.get("version", "")).strip()
    repo_ref = resolve_node_repo_ref(node_repos, key, version)
    lock_entry = lock_by_key.get(key, {})
    source = lock_entry.get("source", {}) if isinstance(lock_entry, dict) else {}
    enabled_in_collection = key in lock_by_key
    repo = str(repo_ref.get("repo", "")).strip()

    repo_status, _repo_payload = _fetch_json(f"https://api.github.com/repos/{repo}")
    repo_exists = repo_status == 200

    latest_release_status = 0
    latest_release_tag = ""
    if repo_exists:
        latest_release_status, latest_release_payload = _fetch_json(
            f"https://api.github.com/repos/{repo}/releases/latest"
        )
        latest_release_tag = str(latest_release_payload.get("tag_name", "")).strip()

    locked_tag = str(source.get("tag", "")).strip()
    locked_asset_name = str(source.get("asset_name", "")).strip()
    release_by_tag_status = 0
    locked_release_exists = False
    locked_asset_exists = False

    if repo_exists and locked_tag:
        release_by_tag_status, release_by_tag_payload = _fetch_json(
            f"https://api.github.com/repos/{repo}/releases/tags/{locked_tag}"
        )
        locked_release_exists = release_by_tag_status == 200
        assets = release_by_tag_payload.get("assets", []) if isinstance(release_by_tag_payload, dict) else []
        if isinstance(assets, list) and locked_asset_name:
            locked_asset_exists = any(
                isinstance(asset, dict) and str(asset.get("name", "")).strip() == locked_asset_name
                for asset in assets
            )

    return {
        "key": key,
        "label": str(entry.get("label", key)).strip() or key,
        "version": version,
        "status": str(entry.get("status", "")).strip(),
        "enabled_in_collection": enabled_in_collection,
        "repo": repo,
        "repo_url": str(repo_ref.get("repo_url", "")).strip(),
        "releases_url": str(repo_ref.get("releases_url", "")).strip(),
        "repo_exists": repo_exists,
        "repo_status": repo_status,
        "latest_release_exists": latest_release_status == 200,
        "latest_release_status": latest_release_status,
        "latest_release_tag": latest_release_tag,
        "locked_tag": locked_tag,
        "locked_asset_name": locked_asset_name,
        "locked_release_exists": locked_release_exists,
        "locked_asset_exists": locked_asset_exists,
        "notes": str(entry.get("notes", "")).strip(),
        "messages": [
            message
            for message in [
                "" if repo_exists else f"Missing GitHub repo: {repo}",
                ""
                if (not enabled_in_collection or locked_release_exists)
                else f"Missing locked release tag: {locked_tag}",
                ""
                if (not enabled_in_collection or not locked_asset_name or locked_asset_exists)
                else f"Missing locked asset: {locked_asset_name}",
            ]
            if message
        ],
    }


def _render_markdown(audit: dict[str, Any]) -> str:
    enabled_nodes = [node for node in audit.get("nodes", []) if node.get("enabled_in_collection")]
    planned_nodes = [node for node in audit.get("nodes", []) if not node.get("enabled_in_collection")]

    lines = [
        "# TCollection: audit des sources GitHub",
        "",
        "Ce document est genere depuis `python tools/audit_node_sources.py`.",
        "",
        "## Nodes actifs",
        "",
        "| Node | Repo | Repo OK | Locked tag | Locked asset | Latest release |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for node in enabled_nodes:
        lines.append(
            "| {label} | [{repo}]({repo_url}) | {repo_ok} | {tag_ok} | {asset_ok} | {latest_tag} |".format(
                label=node["label"],
                repo=node["repo"],
                repo_url=node["repo_url"],
                repo_ok="yes" if node.get("repo_exists") else "no",
                tag_ok=node["locked_tag"] if node.get("locked_release_exists") else f"missing `{node['locked_tag']}`",
                asset_ok=(
                    node["locked_asset_name"]
                    if node.get("locked_asset_exists")
                    else f"missing `{node['locked_asset_name']}`"
                ),
                latest_tag=node.get("latest_release_tag") or "-",
            )
        )

    lines.extend(
        [
            "",
            "## Nodes planifies",
            "",
            "| Node | Repo cible | Repo OK | Latest release | Notes |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for node in planned_nodes:
        lines.append(
            "| {label} | [{repo}]({repo_url}) | {repo_ok} | {latest_tag} | {notes} |".format(
                label=node["label"],
                repo=node["repo"],
                repo_url=node["repo_url"],
                repo_ok="yes" if node.get("repo_exists") else "no",
                latest_tag=node.get("latest_release_tag") or "-",
                notes=node.get("notes") or "-",
            )
        )

    problem_nodes = [node for node in audit.get("nodes", []) if node.get("messages")]
    if problem_nodes:
        lines.extend(["", "## Points a regler", ""])
        for node in problem_nodes:
            lines.append(f"### {node['label']}")
            lines.append("")
            for message in node.get("messages", []):
                lines.append(f"- {message}")
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit GitHub repository health for TCollection node sources.")
    parser.add_argument("--strict-enabled", action="store_true", help="Fail if an enabled node has broken GitHub source metadata.")
    parser.add_argument("--write-json", default=str(AUDIT_JSON_PATH), help="JSON report path.")
    parser.add_argument("--write-md", default=str(AUDIT_DOC_PATH), help="Markdown report path.")
    args = parser.parse_args()

    registry = read_json(REGISTRY_PATH)
    node_repos = read_json(NODE_REPOS_PATH)
    lock = read_json(NODE_LOCK_PATH)
    lock_by_key = {
        str(entry.get("key", "")).strip(): entry
        for entry in lock.get("nodes", [])
        if isinstance(entry, dict) and str(entry.get("key", "")).strip()
    }

    report = {
        "schema_version": "1.0",
        "generated_from_registry_updated_at": registry.get("updated_at", ""),
        "nodes": sorted(
            [
                _audit_node(entry, node_repos, lock_by_key)
                for entry in registry.get("nodes", [])
                if isinstance(entry, dict)
            ],
            key=lambda item: item["key"],
        ),
    }

    json_path = Path(args.write_json).resolve()
    md_path = Path(args.write_md).resolve()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report) + "\n", encoding="utf-8")

    failing_enabled = [
        node
        for node in report["nodes"]
        if node.get("enabled_in_collection")
        and (not node.get("repo_exists") or not node.get("locked_release_exists") or not node.get("locked_asset_exists"))
    ]

    print(f"Wrote node source audit JSON: {json_path}")
    print(f"Wrote node source audit Markdown: {md_path}")

    if args.strict_enabled and failing_enabled:
        raise SystemExit(
            "Enabled node sources are broken: "
            + ", ".join(str(node.get("key", "")).strip() for node in failing_enabled)
        )


if __name__ == "__main__":
    main()
