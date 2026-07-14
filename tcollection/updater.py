"""Update helpers for TCollection managed installs."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import zipfile
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
MANAGED_ROOT_ENV = "TCOLLECTION_MANAGED_ROOT"
UPDATE_CACHE_NAME = "update_check_cache.json"
DEFAULT_UPDATE_CACHE_MINUTES = 30


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


def _update_reason(current_version: str, latest_version: str) -> str:
    current_key = _normalize_version(current_version)
    latest_key = _normalize_version(latest_version)
    if latest_key > current_key:
        return "Update available."
    if latest_key < current_key:
        return "This install is newer than the latest published release."
    return "TCollection is already up to date."


def _read_remote_manifest(manifest_url: str) -> dict[str, Any]:
    request = Request(
        manifest_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "TCollection-Updater",
        },
    )
    with urlopen(request, timeout=5) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _github_api_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "TCollection-Updater",
    }
    token = (
        str(os.environ.get("TCOLLECTION_GITHUB_TOKEN", "")).strip()
        or str(os.environ.get("GITHUB_TOKEN", "")).strip()
        or str(os.environ.get("GH_TOKEN", "")).strip()
    )
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_latest_github_release(repo: str) -> dict[str, Any]:
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = Request(api_url, headers=_github_api_headers())
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
        "reason": _update_reason(current_version, latest_version),
    }


def _expand_user_relative_path(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    home_dir = Path.home()
    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return (home_dir / normalized).resolve()


def _managed_root() -> Path:
    override = str(os.environ.get(MANAGED_ROOT_ENV, "")).strip()
    if override:
        return Path(override).expanduser().resolve()

    config = _load_collection_config()
    updates = dict(config.get("updates", {}))
    download_root_raw = str(updates.get("download_root", ".nuke/TCollection/versions")).strip()
    versions_root = _expand_user_relative_path(download_root_raw)
    return versions_root.parent if versions_root.name == "versions" else versions_root


def _versions_root() -> Path:
    override = str(os.environ.get(MANAGED_ROOT_ENV, "")).strip()
    if override:
        return Path(override).expanduser().resolve() / "versions"

    config = _load_collection_config()
    updates = dict(config.get("updates", {}))
    download_root_raw = str(updates.get("download_root", ".nuke/TCollection/versions")).strip()
    return _expand_user_relative_path(download_root_raw)


def _state_path(name: str) -> Path:
    return _managed_root() / name


def _update_cache_path() -> Path:
    return _state_path(UPDATE_CACHE_NAME)


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _update_cache_ttl_seconds(updates: dict[str, Any]) -> int:
    raw_value = updates.get("cache_ttl_minutes", DEFAULT_UPDATE_CACHE_MINUTES)
    try:
        minutes = max(0, int(float(raw_value)))
    except Exception:
        minutes = DEFAULT_UPDATE_CACHE_MINUTES
    return minutes * 60


def _read_cached_update_result(
    current_version: str,
    channel: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    cache = _read_json_if_exists(_update_cache_path())
    if not cache:
        return None

    if str(cache.get("current_version", "")).strip() != current_version:
        return None
    if str(cache.get("channel", "")).strip() != channel:
        return None

    expires_at = float(cache.get("expires_at", 0) or 0)
    if expires_at <= time.time():
        return None

    result = cache.get("result")
    if not isinstance(result, dict):
        return None

    cached = dict(result)
    cached["cached"] = True
    return cached


def _write_cached_update_result(
    current_version: str,
    channel: str,
    updates: dict[str, Any],
    result: dict[str, Any],
) -> None:
    now = time.time()
    payload = {
        "current_version": current_version,
        "channel": channel,
        "checked_at": now,
        "expires_at": now + _update_cache_ttl_seconds(updates),
        "result": dict(result),
    }
    _write_json(_update_cache_path(), payload)


def _required_entry_paths(base_dir: Path) -> list[Path]:
    return [
        base_dir / "config" / "collection.json",
        base_dir / "tcollection" / "manifest.json",
        base_dir / "init.py",
        base_dir / "menu.py",
    ]


def _is_valid_entry_root(base_dir: Path) -> bool:
    return all(path.is_file() for path in _required_entry_paths(base_dir))


def _candidate_entry_root(base_dir: Path) -> Path | None:
    if not base_dir.exists() or not base_dir.is_dir():
        return None

    if _is_valid_entry_root(base_dir):
        return base_dir

    children = [path for path in base_dir.iterdir() if path.is_dir()]
    for child in sorted(children):
        if _is_valid_entry_root(child):
            return child
    return None


def _entry_root_from_state(managed_root: Path, state: dict[str, Any]) -> Path | None:
    entry_root_raw = str(state.get("entry_root", "")).strip()
    if entry_root_raw:
        return _candidate_entry_root((managed_root / entry_root_raw).resolve())

    version = str(state.get("version", "")).strip()
    if not version:
        return None
    return _candidate_entry_root((_versions_root() / version).resolve())


def get_install_state() -> dict[str, str]:
    managed_root = _managed_root()
    versions_root = _versions_root()
    current = _read_json_if_exists(_state_path("current.json"))
    pending = _read_json_if_exists(_state_path("pending.json"))
    current_entry = _entry_root_from_state(managed_root, current)
    pending_entry = _entry_root_from_state(managed_root, pending)
    return {
        "managed_root": str(managed_root),
        "versions_root": str(versions_root),
        "runtime_root": str(ROOT_DIR),
        "current_version": str(current.get("version", "")).strip(),
        "current_entry_root": str(current_entry) if current_entry else "",
        "pending_version": str(pending.get("version", "")).strip(),
        "pending_entry_root": str(pending_entry) if pending_entry else "",
    }


def describe_install_state() -> str:
    state = get_install_state()
    return (
        "TCollection install status\n\n"
        f"Runtime root: {state['runtime_root']}\n"
        f"Managed root: {state['managed_root']}\n"
        f"Versions root: {state['versions_root']}\n"
        f"Current managed version: {state['current_version'] or '(none)'}\n"
        f"Pending version: {state['pending_version'] or '(none)'}\n"
    )


def _download_file(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "TCollection-Updater"})
    with urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


def _validate_extracted_package(root_dir: Path, version: str) -> Path:
    entry_root = _candidate_entry_root(root_dir)
    if entry_root is None:
        raise RuntimeError(f"Unable to find a TCollection package root in the downloaded archive for {version}.")
    return entry_root


def _stage_version_archive(archive_path: Path, version: str) -> Path:
    with tempfile.TemporaryDirectory(prefix="tcollection_install_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        extract_root = temp_dir / "extract"
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_root)

        entry_root = _validate_extracted_package(extract_root, version)
        final_version_root = _versions_root() / version
        final_version_root.parent.mkdir(parents=True, exist_ok=True)
        if final_version_root.exists():
            shutil.rmtree(final_version_root)
        shutil.move(str(entry_root), str(final_version_root))
        return final_version_root


def check_for_updates(force_refresh: bool = False) -> dict[str, Any]:
    config = _load_collection_config()
    updates = dict(config.get("updates", {}))
    current_version = _current_version()
    channel = str(updates.get("channel", "")).strip()

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

    if not force_refresh:
        cached = _read_cached_update_result(current_version, channel, updates)
        if cached is not None:
            return cached

    if manifest_url:
        try:
            result = _read_remote_manifest(manifest_url)
            latest_version = str(result.get("version", "")).strip() or current_version
            resolved = {
                "available": _normalize_version(latest_version) > _normalize_version(current_version),
                "current_version": current_version,
                "latest_version": latest_version,
                "channel": str(result.get("channel", channel)).strip() or channel,
                "download_url": str(result.get("download_url", "")).strip(),
                "notes_url": str(result.get("notes_url", "")).strip(),
                "reason": _update_reason(current_version, latest_version),
                "cached": False,
            }
            _write_cached_update_result(current_version, channel, updates, resolved)
            return resolved
        except (OSError, URLError, json.JSONDecodeError) as exc:
            return {
                "available": False,
                "current_version": current_version,
                "latest_version": current_version,
                "channel": channel,
                "reason": f"Unable to read remote update manifest: {exc}",
                "cached": False,
            }

    if provider == "github-release":
        try:
            result = _resolve_github_release_result(updates, current_version)
            result["cached"] = False
            _write_cached_update_result(current_version, channel, updates, result)
            return result
        except (OSError, URLError, json.JSONDecodeError) as exc:
            return {
                "available": False,
                "current_version": current_version,
                "latest_version": current_version,
                "channel": channel,
                "reason": f"Unable to read latest GitHub release: {exc}",
                "cached": False,
            }

    if not manifest_url:
        return {
            "available": False,
            "current_version": current_version,
            "latest_version": current_version,
            "channel": channel,
            "reason": "No remote update manifest URL is configured yet.",
            "cached": False,
        }
    return {
        "available": False,
        "current_version": current_version,
        "latest_version": current_version,
        "channel": channel,
        "reason": "No update provider is configured yet.",
        "cached": False,
    }


def prepare_update_for_next_launch(update_result: dict[str, Any] | None = None) -> dict[str, Any]:
    result = dict(update_result or check_for_updates())
    latest_version = str(result.get("latest_version", "")).strip()
    download_url = str(result.get("download_url", "")).strip()
    if not latest_version or not download_url:
        raise RuntimeError("Update metadata is incomplete. Missing latest_version or download_url.")

    managed_root = _managed_root()
    versions_root = _versions_root()
    managed_root.mkdir(parents=True, exist_ok=True)
    versions_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tcollection_download_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        archive_path = temp_dir / f"TCollection-v{latest_version}.zip"
        _download_file(download_url, archive_path)
        final_version_root = _stage_version_archive(archive_path, latest_version)

    payload = {
        "version": latest_version,
        "entry_root": str(final_version_root.relative_to(managed_root)).replace("\\", "/"),
        "download_url": download_url,
        "notes_url": str(result.get("notes_url", "")).strip(),
    }

    config = _load_collection_config()
    activate_on_next_launch = bool(dict(config.get("updates", {})).get("activate_on_next_launch", True))
    if activate_on_next_launch:
        _write_json(_state_path("pending.json"), payload)
    else:
        _write_json(_state_path("current.json"), payload)

    return {
        "prepared": True,
        "version": latest_version,
        "managed_root": str(managed_root),
        "version_root": str(final_version_root),
        "restart_required": activate_on_next_launch,
        "notes_url": payload["notes_url"],
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
        startup_prompt = bool(updates.get("startup_prompt", False))
        if startup_prompt and hasattr(nuke, "ask") and nuke.ask(  # ty: ignore[unresolved-attribute]
            "TCollection update available.\n\n"
            f"Current: {result['current_version']}\n"
            f"Latest: {result['latest_version']}\n\n"
            "Download now and activate on next launch?"
        ):
            prepared = prepare_update_for_next_launch(result)
            nuke.message(  # ty: ignore[unresolved-attribute]
                "TCollection update prepared.\n\n"
                f"Version: {prepared['version']}\n"
                "Restart Nuke to activate it."
            )
        elif not background:
            nuke.message(message)  # ty: ignore[unresolved-attribute]
    else:
        print(message)
