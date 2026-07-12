"""Stable bootstrap helpers for managed TCollection installs in Nuke."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
MANAGED_ROOT_ENV = "TCOLLECTION_MANAGED_ROOT"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _expand_user_relative_path(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    home_dir = Path.home()
    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return (home_dir / normalized).resolve()


def _required_entry_paths(base_dir: Path) -> list[Path]:
    return [
        base_dir / "config" / "collection.json",
        base_dir / "tcollection" / "manifest.json",
        base_dir / "init.py",
        base_dir / "menu.py",
    ]


def _is_valid_entry_root(base_dir: Path) -> bool:
    return all(path.is_file() for path in _required_entry_paths(base_dir))


def _managed_root_from_local_config() -> Path:
    override = str(os.environ.get(MANAGED_ROOT_ENV, "")).strip()
    if override:
        return Path(override).expanduser().resolve()

    config_path = ROOT_DIR / "config" / "collection.json"
    if config_path.is_file():
        config = _read_json(config_path)
        updates = config.get("updates", {})
        if isinstance(updates, dict):
            download_root_raw = str(updates.get("download_root", "")).strip()
            if download_root_raw:
                versions_root = _expand_user_relative_path(download_root_raw)
                return versions_root.parent if versions_root.name == "versions" else versions_root

    return (Path.home() / ".nuke" / "TCollection").resolve()


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


def _state_entry_root(managed_root: Path, state: dict[str, Any]) -> Path | None:
    entry_root_raw = str(state.get("entry_root", "")).strip()
    if entry_root_raw:
        candidate = (managed_root / entry_root_raw).resolve()
        return _candidate_entry_root(candidate)

    version = str(state.get("version", "")).strip()
    if not version:
        return None

    return _candidate_entry_root((managed_root / "versions" / version).resolve())


def _promote_pending_if_ready(managed_root: Path) -> None:
    pending_path = managed_root / "pending.json"
    current_path = managed_root / "current.json"
    pending = _read_json(pending_path)
    if not pending:
        return

    entry_root = _state_entry_root(managed_root, pending)
    if entry_root is None:
        return

    payload = dict(pending)
    payload["entry_root"] = str(entry_root.relative_to(managed_root)).replace("\\", "/")
    _write_json(current_path, payload)
    try:
        pending_path.unlink()
    except FileNotFoundError:
        pass


def resolve_runtime_root() -> Path:
    managed_root = _managed_root_from_local_config()
    _promote_pending_if_ready(managed_root)

    current = _read_json(managed_root / "current.json")
    entry_root = _state_entry_root(managed_root, current)
    if entry_root is not None and entry_root.resolve() != ROOT_DIR.resolve():
        return entry_root
    return ROOT_DIR


def ensure_runtime_on_sys_path() -> Path:
    runtime_root = resolve_runtime_root()
    runtime_str = str(runtime_root)
    if runtime_str not in sys.path:
        sys.path.insert(0, runtime_str)
    return runtime_root


def load_runtime_callable(module_name: str, attribute: str) -> tuple[Any, Path]:
    runtime_root = ensure_runtime_on_sys_path()
    module = importlib.import_module(module_name)
    return getattr(module, attribute, None), runtime_root


def get_bootstrap_state() -> dict[str, str]:
    managed_root = _managed_root_from_local_config()
    runtime_root = resolve_runtime_root()
    current = _read_json(managed_root / "current.json")
    pending = _read_json(managed_root / "pending.json")
    return {
        "managed_root": str(managed_root),
        "runtime_root": str(runtime_root),
        "current_version": str(current.get("version", "")).strip(),
        "pending_version": str(pending.get("version", "")).strip(),
    }
