"""Update manifest helpers for TCollection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    import nuke  # ty: ignore[unresolved-import]
except Exception:  # pragma: no cover - available only in Nuke runtime
    nuke = None  # type: ignore[assignment]

ROOT_DIR = Path(__file__).resolve().parents[1]
COLLECTION_CONFIG_PATH = ROOT_DIR / "config" / "collection.json"
VERSION_PATH = ROOT_DIR / "VERSION"


def _load_collection_config() -> dict[str, Any]:
    return json.loads(COLLECTION_CONFIG_PATH.read_text(encoding="utf-8"))


def _normalize_version(version: str) -> tuple[int, ...]:
    cleaned = version.strip().lower().removeprefix("v")
    parts: list[int] = []
    for token in cleaned.split("."):
        try:
            parts.append(int(token))
        except ValueError:
            break
    return tuple(parts)


def _current_version() -> str:
    return VERSION_PATH.read_text(encoding="utf-8").strip()


def _read_remote_manifest(manifest_url: str) -> dict[str, Any]:
    with urlopen(manifest_url, timeout=5) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _read_latest_github_release(repo: str) -> dict[str, Any]:
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "TCollection-Updater",
        },
    )
    with urlopen(request, timeout=5) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _resolve_github_release_result(
    updates: dict[str, Any],
    current_version: str,
) -> dict[str, Any]:
    repo = str(updates.get("repo", "")).strip()
    if not repo:
        return {
            "available": False,
            "current_version": current_version,
            "latest_version": current_version,
            "channel": str(updates.get("channel", "")),
            "reason": "No GitHub repo is configured for update checks.",
        }

    release = _read_latest_github_release(repo)
    latest_version = str(release.get("tag_name", "")).strip().removeprefix("v") or current_version
    asset_pattern = str(updates.get("asset_name_pattern", "TCollection-v{version}.zip"))
    expected_asset_name = asset_pattern.format(version=latest_version)

    download_url = ""
    for asset in release.get("assets", []):
        if not isinstance(asset, dict):
            continue
        if str(asset.get("name", "")).strip() == expected_asset_name:
            download_url = str(asset.get("browser_download_url", "")).strip()
            break

    available = _normalize_version(latest_version) > _normalize_version(current_version)
    return {
        "available": available,
        "current_version": current_version,
        "latest_version": latest_version,
        "channel": str(updates.get("channel", "")),
        "download_url": download_url,
        "notes_url": str(release.get("html_url", "")).strip(),
        "reason": "Update available." if available else "TCollection is already up to date.",
    }


def check_for_updates() -> dict[str, Any]:
    config = _load_collection_config()
    updates = dict(config.get("updates", {}))
    current_version = _current_version()

    if not updates.get("enabled", False):
        return {
            "available": False,
            "current_version": current_version,
            "latest_version": current_version,
            "channel": "",
            "reason": "Update checks are disabled in config/collection.json.",
        }

    manifest_url = str(updates.get("manifest_url", "")).strip()
    provider = str(updates.get("provider", "")).strip().lower()
    if provider == "github-release":
        try:
            return _resolve_github_release_result(updates, current_version)
        except (OSError, URLError, json.JSONDecodeError) as exc:
            return {
                "available": False,
                "current_version": current_version,
                "latest_version": current_version,
                "channel": str(updates.get("channel", "")),
                "reason": f"Unable to read latest GitHub release: {exc}",
            }

    if not manifest_url:
        return {
            "available": False,
            "current_version": current_version,
            "latest_version": current_version,
            "channel": str(updates.get("channel", "")),
            "reason": "No remote update manifest URL is configured yet.",
        }

    try:
        remote = _read_remote_manifest(manifest_url)
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "current_version": current_version,
            "latest_version": current_version,
            "channel": str(updates.get("channel", "")),
            "reason": f"Unable to read remote update manifest: {exc}",
        }

    latest_version = str(remote.get("version", "")).strip() or current_version
    available = _normalize_version(latest_version) > _normalize_version(current_version)
    return {
        "available": available,
        "current_version": current_version,
        "latest_version": latest_version,
        "channel": str(remote.get("channel", updates.get("channel", ""))),
        "download_url": str(remote.get("download_url", "")).strip(),
        "notes_url": str(remote.get("notes_url", "")).strip(),
        "reason": "Update available." if available else "TCollection is already up to date.",
    }


def notify_startup_update(background: bool = True) -> None:
    config = _load_collection_config()
    updates = dict(config.get("updates", {}))
    if not updates.get("startup_check", False):
        return

    result = check_for_updates()
    if not result["available"]:
        return

    message = (
        "[TCollection] Update available: "
        f"{result['current_version']} -> {result['latest_version']}"
    )
    if nuke is not None:
        nuke.tprint(message)
        if not background:
            nuke.message(message)  # ty: ignore[unresolved-attribute]
    else:
        print(message)
