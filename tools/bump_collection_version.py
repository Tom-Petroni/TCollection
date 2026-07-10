"""Bump the TCollection version in VERSION and config/collection.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT_DIR / "VERSION"
COLLECTION_CONFIG_PATH = ROOT_DIR / "config" / "collection.json"


def _parse(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.strip().split(".")
    return int(major), int(minor), int(patch)


def _format(version: tuple[int, int, int]) -> str:
    return f"{version[0]}.{version[1]}.{version[2]}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump the TCollection version.")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    parser.add_argument("--set-version", default="", help="Explicit version override.")
    args = parser.parse_args()

    if args.set_version:
        next_version = args.set_version.strip()
    else:
        major, minor, patch = _parse(VERSION_PATH.read_text(encoding="utf-8").strip())
        if args.bump == "major":
            major, minor, patch = major + 1, 0, 0
        elif args.bump == "minor":
            minor, patch = minor + 1, 0
        else:
            patch += 1
        next_version = _format((major, minor, patch))

    VERSION_PATH.write_text(f"{next_version}\n", encoding="utf-8")

    config = json.loads(COLLECTION_CONFIG_PATH.read_text(encoding="utf-8"))
    config["version"] = next_version
    COLLECTION_CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Bumped TCollection version to {next_version}")


if __name__ == "__main__":
    main()

