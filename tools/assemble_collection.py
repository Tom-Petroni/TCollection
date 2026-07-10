"""Assemble a local TCollection package from sibling node repositories."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from _collection_utils import (
    COLLECTION_CONFIG_PATH,
    NODE_LOCK_PATH,
    ROOT_DIR,
    prune_pycache,
    read_json,
    read_version,
    resolve_repo_path,
)

PACKAGE_ROOT_FILES = [
    "init.py",
    "menu.py",
    "tcollection_bootstrap.py",
    "VERSION",
]

PACKAGE_ROOT_DIRS = [
    "config",
    "docs",
    "gizmos",
    "scripts",
    "tcollection",
]


def _selected_statuses(raw_statuses: str) -> set[str]:
    return {token.strip() for token in raw_statuses.split(",") if token.strip()}


def _parse_archive_overrides(raw_values: list[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for raw_value in raw_values:
        token = raw_value.strip()
        if not token:
            continue
        node_key, separator, archive_path = token.partition("=")
        if not separator or not node_key.strip() or not archive_path.strip():
            raise ValueError(
                "Archive overrides must use the format NODE_KEY=/absolute/or/relative/path.zip"
            )
        overrides[node_key.strip()] = Path(archive_path.strip()).resolve()
    return overrides


def _iter_registry_nodes(statuses: set[str]) -> list[dict[str, Any]]:
    registry = read_json(ROOT_DIR / "nodes" / "registry.json")
    lock = read_json(ROOT_DIR / "config" / "node_lock.json")
    locked_keys = {
        str(entry.get("key", "")).strip()
        for entry in lock.get("nodes", [])
        if isinstance(entry, dict) and str(entry.get("key", "")).strip()
    }
    nodes = []
    for entry in registry.get("nodes", []):
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key", "")).strip()
        status = str(entry.get("status", "")).strip()
        if not key or key not in locked_keys:
            continue
        if statuses and status not in statuses:
            continue
        nodes.append(entry)
    return nodes


def _iter_locked_nodes(statuses: set[str]) -> list[dict[str, Any]]:
    lock = read_json(NODE_LOCK_PATH)
    nodes = []
    for entry in lock.get("nodes", []):
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "")).strip()
        if statuses and status not in statuses:
            continue
        nodes.append(entry)
    return nodes


def _copy_runtime_root(stage_dir: Path) -> None:
    for relative in PACKAGE_ROOT_FILES:
        src = ROOT_DIR / relative
        dst = stage_dir / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for relative in PACKAGE_ROOT_DIRS:
        src = ROOT_DIR / relative
        dst = stage_dir / relative
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def _copy_node_publish(stage_dir: Path, node_key: str, repo_path: Path) -> None:
    publish_src = repo_path / "publish"
    if not publish_src.is_dir():
        raise FileNotFoundError(f"Missing publish directory for {node_key}: {publish_src}")

    publish_dst = stage_dir / "nodes" / node_key / "publish"
    if publish_dst.exists():
        shutil.rmtree(publish_dst)
    publish_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(publish_src, publish_dst)


def _download_release_asset(repo: str, tag: str, asset_name: str, destination: Path) -> None:
    url = f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"
    request = Request(url, headers={"User-Agent": "TCollection-Assembler"})
    with urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


def _extract_release_publish(stage_dir: Path, node_key: str, archive_path: Path) -> None:
    publish_dst = stage_dir / "nodes" / node_key / "publish"
    if publish_dst.exists():
        shutil.rmtree(publish_dst)
    publish_dst.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(publish_dst)


def _infer_bootstrap_module(node_key: str, publish_dir: Path, fallback: str) -> str:
    expected = publish_dir / node_key / "init.py"
    if expected.is_file():
        return f"{node_key}.init"

    child_dirs = [path for path in publish_dir.iterdir() if path.is_dir() and (path / "init.py").is_file()]
    if len(child_dirs) == 1:
        return f"{child_dirs[0].name}.init"

    return fallback


def _build_packaged_manifest(stage_dir: Path, included_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    collection = read_json(COLLECTION_CONFIG_PATH)
    packaged_nodes = []
    for entry in included_nodes:
        node_key = str(entry.get("key", "")).strip()
        publish_dir = stage_dir / "nodes" / node_key / "publish"
        packaged_entry = dict(entry)
        packaged_entry["python_path"] = f"nodes/{node_key}/publish"
        packaged_entry["bootstrap_module"] = _infer_bootstrap_module(
            node_key,
            publish_dir,
            str(entry.get("bootstrap_module", "")).strip(),
        )
        packaged_nodes.append(packaged_entry)

    return {
        "collection": {
            "key": collection.get("key", "TCollection"),
            "display_name": collection.get("display_name", "TCollection"),
            "version": collection.get("version", "0.0.0"),
            "status": collection.get("status", "unknown"),
        },
        "nodes": packaged_nodes,
    }


def _write_packaged_manifest(stage_dir: Path, included_nodes: list[dict[str, Any]], version: str) -> None:
    manifest = _build_packaged_manifest(stage_dir, included_nodes)
    manifest["collection"]["version"] = version
    manifest_path = stage_dir / "tcollection" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _write_update_manifest(
    output_dir: Path,
    package_name: str,
    version: str,
    download_url: str,
    notes_url: str,
) -> Path:
    collection = read_json(COLLECTION_CONFIG_PATH)
    manifest = {
        "key": collection.get("key", "TCollection"),
        "channel": str(collection.get("updates", {}).get("channel", "stable")),
        "version": version,
        "download_url": download_url or f"./{package_name}",
        "notes_url": notes_url,
    }
    manifest_path = output_dir / "latest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _sha256_for(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_sha256sums(output_dir: Path, paths: list[Path]) -> Path:
    lines = [f"{_sha256_for(path)}  {path.name}" for path in paths]
    checksum_path = output_dir / "SHA256SUMS.txt"
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir():
                continue
            archive.write(path, arcname=path.relative_to(source_dir))


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble a local TCollection package.")
    parser.add_argument(
        "--source",
        choices=["local", "github-release"],
        default="local",
        help="Assemble from sibling repos or from node GitHub release assets.",
    )
    parser.add_argument("--statuses", default="stable", help="Comma-separated node statuses to include.")
    parser.add_argument("--output", default="dist", help="Output directory relative to the repo root.")
    parser.add_argument("--package-version", default="", help="Optional package version override.")
    parser.add_argument("--download-url", default="", help="Explicit absolute download URL for latest.json.")
    parser.add_argument("--notes-url", default="", help="Explicit release notes URL for latest.json.")
    parser.add_argument(
        "--archive-override",
        action="append",
        default=[],
        help="Optional local archive override in the form NODE_KEY=path/to/release.zip. Repeat per node.",
    )
    args = parser.parse_args()

    statuses = _selected_statuses(args.statuses)
    archive_overrides = _parse_archive_overrides(args.archive_override)
    version = args.package_version.strip() or read_version()
    output_dir = (ROOT_DIR / args.output).resolve()
    stage_dir = output_dir / f"TCollection-{version}"
    zip_path = output_dir / f"TCollection-v{version}.zip"

    output_dir.mkdir(parents=True, exist_ok=True)
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    _copy_runtime_root(stage_dir)
    included_node_entries: list[dict[str, Any]] = []

    if args.source == "local":
        for entry in _iter_registry_nodes(statuses):
            node_key = str(entry.get("key", "")).strip()
            if not node_key:
                continue
            archive_override = archive_overrides.get(node_key)
            if archive_override is not None:
                _extract_release_publish(stage_dir, node_key, archive_override)
            else:
                repo_path = resolve_repo_path(node_key)
                _copy_node_publish(stage_dir, node_key, repo_path)
            included_node_entries.append(entry)
    else:
        registry_by_key = {
            str(entry.get("key", "")).strip(): entry
            for entry in _iter_registry_nodes(statuses)
            if isinstance(entry, dict) and str(entry.get("key", "")).strip()
        }
        with tempfile.TemporaryDirectory(prefix="tcollection_release_") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            for entry in _iter_locked_nodes(statuses):
                node_key = str(entry.get("key", "")).strip()
                if not node_key:
                    continue
                source = entry.get("source", {})
                if not isinstance(source, dict):
                    continue
                repo = str(source.get("repo", "")).strip()
                tag = str(source.get("tag", "")).strip()
                asset_name = str(source.get("asset_name", "")).strip()
                archive_path = temp_dir / asset_name
                _download_release_asset(repo, tag, asset_name, archive_path)
                _extract_release_publish(stage_dir, node_key, archive_path)
                if node_key in registry_by_key:
                    included_node_entries.append(registry_by_key[node_key])

    prune_pycache(stage_dir)
    _write_packaged_manifest(stage_dir, included_node_entries, version)

    if zip_path.exists():
        zip_path.unlink()
    _zip_dir(stage_dir, zip_path)
    manifest_path = _write_update_manifest(
        output_dir,
        zip_path.name,
        version,
        args.download_url.strip(),
        args.notes_url.strip(),
    )
    checksum_path = _write_sha256sums(output_dir, [zip_path, manifest_path])

    print(f"Staged collection directory: {stage_dir}")
    print(f"Created collection archive: {zip_path}")
    print(f"Created update manifest: {manifest_path}")
    print(f"Created checksums: {checksum_path}")
    print(
        "Included nodes: "
        + (
            ", ".join(str(entry.get("key", "")).strip() for entry in included_node_entries)
            if included_node_entries
            else "(none)"
        )
    )


if __name__ == "__main__":
    main()
