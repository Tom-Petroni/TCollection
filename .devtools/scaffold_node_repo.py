#!/usr/bin/env python3
"""Scaffold a new TCollection native Nuke node repository.

The scaffold intentionally starts from the proven CPU-native infra already used
by the current node repos:

- GitHub Actions workflows
- xtask build helper
- package import validation
- runtime smoke script

The generated repo is ready for a fast local loop on Nuke and for later
promotion into TCollection.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_SOURCE = ROOT.parent / "TColorRamp"

COPY_SEED_PATHS = (
    Path(".github/workflows/nuke-build.yml"),
    Path(".github/workflows/nuke-runtime-smoke.yml"),
    Path(".github/workflows/version-tag.yml"),
    Path(".gitignore"),
    Path("config/nuke_versions.json"),
    Path("tools/Get-NukeBuildMatrix.ps1"),
    Path("work/.cargo/config.toml"),
    Path("work/scripts/runtime_smoke.py"),
    Path("work/scripts/validate_package_import.py"),
    Path("work/xtask"),
)

TEXT_SUFFIXES = {
    "",
    ".cpp",
    ".gitignore",
    ".json",
    ".lock",
    ".md",
    ".ps1",
    ".py",
    ".rs",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}

VALID_STATUSES = {"stable", "test", "hold"}
NODE_KEY_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def die(message: str) -> "NoReturn":
    raise SystemExit(message)


def camel_to_snake(value: str) -> str:
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def node_to_snake(node_key: str) -> str:
    if node_key.startswith("T") and len(node_key) > 1 and node_key[1:].isalnum():
        return f"t{camel_to_snake(node_key[1:])}"
    return camel_to_snake(node_key)


def build_name_variants(node_key: str) -> dict[str, str]:
    node_lower = node_key.lower()
    node_snake = node_to_snake(node_key)
    return {
        "key": node_key,
        "lower": node_lower,
        "snake": node_snake,
        "env": node_key.upper(),
        "crate_name": f"{node_lower}-nuke",
        "lib_name": f"{node_lower}_nuke",
        "cfg_name": f"{node_snake}_native",
        "cpp_file": f"{node_snake}.cpp",
        "rust_link_fn": f"{node_snake}_rust_link",
        "keepalive_fn": f"{node_snake}_keepalive",
    }


def replace_tokens(raw: str, mapping: dict[str, str]) -> str:
    rendered = raw
    for key, value in mapping.items():
        rendered = rendered.replace(key, value)
    return rendered


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def copy_seed_paths(seed_root: Path, output_root: Path) -> None:
    missing: list[str] = []
    for relative_path in COPY_SEED_PATHS:
        source_path = seed_root / relative_path
        if not source_path.exists():
            missing.append(str(relative_path))
            continue

        destination_path = output_root / relative_path
        if source_path.is_dir():
            shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
        else:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)

    if missing:
        missing_list = "\n".join(f"- {item}" for item in missing)
        die(
            "Template source is missing required scaffold files:\n"
            f"{missing_list}\n\n"
            f"Template source checked: {seed_root}"
        )


def read_seed_node_key(seed_root: Path) -> str:
    node_json_path = seed_root / "node.json"
    if node_json_path.is_file():
        try:
            payload = json.loads(node_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            die(f"Unable to parse template source node.json: {error}")
        key = str(payload.get("key", "")).strip()
        if key:
            return key
    return seed_root.name


def read_seed_build_config(seed_root: Path) -> dict[str, object]:
    build_config_path = seed_root / "node_build_config.json"
    if not build_config_path.is_file():
        return {
            "node": {
                "class_name": "TemplateNode",
                "type": "Iop",
                "version": "0.1.0",
                "vendor": "Thomas Petroni",
            },
            "build": {
                "backend_mode": "CPU",
                "legacy_profile": "CPUOnly",
                "native_build_required": True,
                "cuda_enabled": False,
                "cuda_required": False,
                "work_root": "work",
                "package_dir": "work/TemplateNode",
                "versions_config": "config/nuke_versions.json",
            },
        }

    try:
        return json.loads(build_config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        die(f"Unable to parse template source node_build_config.json: {error}")


def validate_args(args: argparse.Namespace) -> None:
    if not NODE_KEY_RE.match(args.node_key):
        die("Node key must look like 'TMyNode' and contain only letters/digits.")
    if not SEMVER_RE.match(args.version):
        die("Version must use SemVer X.Y.Z.")
    if args.status not in VALID_STATUSES:
        die(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}")
    if not args.menu_path.strip():
        die("Menu path cannot be empty.")


def render_root_init() -> str:
    return dedent(
        """
        \"\"\"__NODE_KEY__ init.py to load plugin in Nuke.\"\"\"

        import os

        import nuke  # ty: ignore[unresolved-import]

        _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
        nuke.pluginAddPath(  # ty: ignore[unresolved-attribute]
            os.path.join(_THIS_DIR, "__NODE_KEY__").replace(os.sep, "/"),
        )
        """
    )


def render_package_init() -> str:
    return dedent(
        """
        \"\"\"Main entry point for __NODE_KEY__ Nuke plugin.\"\"\"

        import logging
        import os

        import nuke  # ty: ignore[unresolved-import]

        try:
            from __NODE_KEY__._plugin_loader import add_plugin_path_safe
        except Exception:
            from _plugin_loader import add_plugin_path_safe

        logger = logging.getLogger(__name__)

        _HOOKS_ENV_VAR = "__NODE_ENV___SCRIPT_HOOKS_DONE"


        def _refresh_plugin_path() -> None:
            loaded = add_plugin_path_safe()
            if not loaded:
                nuke.tprint("[__NODE_KEY__] Plugin binary not loaded yet.")


        def _register_script_hooks() -> None:
            if os.getenv(_HOOKS_ENV_VAR) == "1":
                return

            for hook_name in ("addBeforeScriptLoad", "addOnScriptNew", "addOnScriptLoad"):
                hook = getattr(nuke, hook_name, None)
                if callable(hook):
                    hook(_refresh_plugin_path)

            os.environ[_HOOKS_ENV_VAR] = "1"


        try:
            _register_script_hooks()
            _refresh_plugin_path()
        except Exception:  # pragma: no cover - Nuke runtime dependency
            logger.exception("Unexpected failure while initializing the __NODE_KEY__ plugin.")
        """
    )


def render_package_menu() -> str:
    return dedent(
        """
        \"\"\"Plugin creation script for __NODE_KEY__ menu in Nuke.\"\"\"

        import logging

        try:
            from __NODE_KEY__._menu_creator import add_menu
        except Exception:
            from _menu_creator import add_menu

        logger = logging.getLogger(__name__)

        try:
            add_menu()
        except Exception:  # pragma: no cover - Nuke runtime dependency
            logger.exception("Unexpected failure while creating the __NODE_KEY__ menu.")
        """
    )


def render_package_consts() -> str:
    return dedent(
        """
        \"\"\"Shared product constants for the __NODE_KEY__ Nuke plugin.\"\"\"

        from __future__ import annotations

        import os
        from pathlib import Path

        PACKAGE_PATH = Path(__file__).resolve().parent
        INSTALLATION_PATH = str(PACKAGE_PATH)
        RESOURCES_PATH = str(PACKAGE_PATH / "resources")

        PRODUCT_NAME = "__NODE_KEY__"
        PRODUCT_VERSION = "__NODE_VERSION__"
        PRODUCT_RELEASE_YEAR = "2026"
        PRODUCT_VENDOR = "__NODE_VENDOR__"
        PRODUCT_VENDOR_URL = "__NODE_VENDOR_URL__"

        NODE_CLASS_NAME = PRODUCT_NAME
        MENU_NAME = PRODUCT_NAME
        PLUGIN_BIN_DIRECTORY = "bin"
        ICON_FILENAME = ""

        PLUGIN_LOADED_ENV_VAR = "__NODE_ENV___LOADED"
        PLUGIN_BINARY_PATH_ENV_VAR = "__NODE_ENV___PLUGIN_BIN_PATH"
        HOOKS_SETUP_ENV_VAR = "__NODE_ENV___HOOKS_SETUP"
        RESOURCE_PATH_ADDED_ENV_VAR = "__NODE_ENV___RESOURCE_PATH"


        def normalized_path(path: str) -> str:
            \"\"\"Normalize a filesystem path for Nuke plugin registration.\"\"\"
            return path.replace(os.sep, "/")


        def product_credits_html() -> str:
            \"\"\"Return the shared rich-text credits label shown in the node UI.\"\"\"
            return (
                f"{PRODUCT_NAME} {PRODUCT_VERSION} - {PRODUCT_RELEASE_YEAR} - "
                f"<a href='{PRODUCT_VENDOR_URL}' "
                "style='text-decoration: underline; color: #9ec3ff;'>"
                f"{PRODUCT_VENDOR}"
                "</a>"
            )
        """
    )


def render_package_credits_link() -> str:
    return dedent(
        """
        \"\"\"Inline credits link widget for __NODE_KEY__ knobs.\"\"\"

        from __future__ import annotations

        import webbrowser

        try:
            from __NODE_KEY__._consts import product_credits_html
        except Exception:
            from _consts import product_credits_html

        try:
            from PySide2 import QtCore, QtWidgets  # ty:ignore[import-not-found]
        except Exception:  # pragma: no cover - Nuke runtime dependency
            try:
                from PySide6 import QtCore, QtWidgets  # ty:ignore[import-not-found]
            except Exception:  # pragma: no cover - Nuke runtime dependency
                QtCore = None
                QtWidgets = None

        _CREDITS_HTML = product_credits_html()


        if QtWidgets is not None:

            class _CreditsLinkWidget(QtWidgets.QWidget):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setSizePolicy(
                        QtWidgets.QSizePolicy(
                            QtWidgets.QSizePolicy.Preferred,
                            QtWidgets.QSizePolicy.Fixed,
                        ),
                    )

                    layout = QtWidgets.QHBoxLayout(self)
                    layout.setContentsMargins(0, 0, 0, 0)
                    layout.setSpacing(0)

                    self._label = QtWidgets.QLabel(_CREDITS_HTML, self)
                    self._label.setTextFormat(QtCore.Qt.RichText)
                    self._label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
                    self._label.setOpenExternalLinks(False)
                    self._label.setStyleSheet("QLabel { background: transparent; border: none; }")
                    self._label.linkActivated.connect(self._open_link)
                    self._label.setSizePolicy(
                        QtWidgets.QSizePolicy(
                            QtWidgets.QSizePolicy.Maximum,
                            QtWidgets.QSizePolicy.Fixed,
                        ),
                    )

                    layout.addWidget(self._label)
                    layout.addStretch(1)

                    fixed_h = max(18, int(self._label.sizeHint().height()) + 2)
                    self.setMinimumHeight(fixed_h)
                    self.setMaximumHeight(fixed_h)

                def _open_link(self, link: str) -> None:
                    webbrowser.open(link)


        class __NODE_KEY__CreditsLinkKnob:
            \"\"\"Bridge object used by Nuke PythonKnob/PyCustom to create credit link UI.\"\"\"

            def makeUI(self):
                if QtWidgets is None:
                    return None
                return _CreditsLinkWidget()
        """
    )


def render_package_menu_creator() -> str:
    return dedent(
        """
        \"\"\"Functions that handle creation of the Nuke menu.\"\"\"

        import logging
        import os

        import nuke  # ty: ignore[unresolved-import]

        try:
            from __NODE_KEY__._consts import (
                ICON_FILENAME,
                MENU_NAME,
                NODE_CLASS_NAME,
                PLUGIN_LOADED_ENV_VAR,
                RESOURCE_PATH_ADDED_ENV_VAR,
                RESOURCES_PATH,
                normalized_path,
            )
            from __NODE_KEY__._plugin_loader import ensure_node_class_loaded
        except Exception:
            from _consts import (
                ICON_FILENAME,
                MENU_NAME,
                NODE_CLASS_NAME,
                PLUGIN_LOADED_ENV_VAR,
                RESOURCE_PATH_ADDED_ENV_VAR,
                RESOURCES_PATH,
                normalized_path,
            )
            from _plugin_loader import ensure_node_class_loaded

        logger = logging.getLogger(__name__)


        def create_node():
            \"\"\"Create node and force-load plugin binary first.\"\"\"
            try:
                ensure_node_class_loaded()
                nuke.createNode(NODE_CLASS_NAME)
            except Exception as error:
                nuke.tprint("[__NODE_KEY__] Unable to create node '{}': {}".format(NODE_CLASS_NAME, error))


        def _create_menu():
            \"\"\"Create the Nuke menu and add the command.\"\"\"
            toolbar = nuke.menu("Nodes")
            menu = toolbar.findItem(MENU_NAME)
            if menu is None:
                if ICON_FILENAME:
                    menu = toolbar.addMenu(MENU_NAME, ICON_FILENAME)
                else:
                    menu = toolbar.addMenu(MENU_NAME)

            command_path = "{}/{}".format(MENU_NAME, NODE_CLASS_NAME)
            if toolbar.findItem(command_path) is None:
                callback = "import {} as _menu_module; _menu_module.create_node()".format(__name__)
                if ICON_FILENAME:
                    menu.addCommand(
                        NODE_CLASS_NAME,
                        callback,
                        icon=ICON_FILENAME,
                    )
                else:
                    menu.addCommand(
                        NODE_CLASS_NAME,
                        callback,
                    )


        def add_menu():
            \"\"\"Always create the menu; log plugin load state for diagnostics.\"\"\"
            _add_menu_dependencies_to_plugin_path()
            _create_menu()

            if os.getenv(PLUGIN_LOADED_ENV_VAR) != "1":
                logger.warning("__NODE_KEY__ menu created, but plugin binary is not loaded yet.")


        def _add_menu_dependencies_to_plugin_path():
            resources_path = normalized_path(RESOURCES_PATH)
            if os.getenv(RESOURCE_PATH_ADDED_ENV_VAR) == resources_path:
                return

            nuke.pluginAppendPath(resources_path)
            os.environ[RESOURCE_PATH_ADDED_ENV_VAR] = resources_path
        """
    )


def render_package_plugin_loader() -> str:
    return dedent(
        """
        \"\"\"Plugin loader and lookup script.\"\"\"

        from __future__ import annotations

        import logging
        import os
        import platform

        import nuke  # ty: ignore[unresolved-import]

        try:
            from __NODE_KEY__._consts import (
                INSTALLATION_PATH,
                NODE_CLASS_NAME,
                PLUGIN_BIN_DIRECTORY,
                PLUGIN_BINARY_PATH_ENV_VAR,
                PLUGIN_LOADED_ENV_VAR,
                normalized_path,
            )
        except Exception:
            from _consts import (
                INSTALLATION_PATH,
                NODE_CLASS_NAME,
                PLUGIN_BIN_DIRECTORY,
                PLUGIN_BINARY_PATH_ENV_VAR,
                PLUGIN_LOADED_ENV_VAR,
                normalized_path,
            )

        logger = logging.getLogger(__name__)

        NUKE_ARM_VERSION = 15
        \"\"\"First Nuke major version that has ARM support.\"\"\"


        class PluginNotFoundError(Exception):
            \"\"\"Raised when the plugin path is not found.\"\"\"


        class PluginLoadError(Exception):
            \"\"\"Raised when the plugin binary cannot be loaded.\"\"\"


        class UnsupportedSystemError(Exception):
            \"\"\"Raised when the operating system is not supported.\"\"\"


        def _get_nuke_version():
            \"\"\"Return the Nuke version in Major.Minor format.\"\"\"
            return "{}.{}".format(nuke.NUKE_VERSION_MAJOR, nuke.NUKE_VERSION_MINOR)


        def _machine_name():
            \"\"\"Return a normalized machine identifier for the current host.\"\"\"
            return (platform.machine() or platform.processor() or "").strip().lower()


        def _get_operating_system_name():
            \"\"\"Return the OS name matching package folders.\"\"\"
            operating_system = platform.system().lower()

            if "linux" in operating_system:
                return "linux"
            if "windows" in operating_system:
                return "windows"
            if "darwin" in operating_system:
                return "macos"

            raise UnsupportedSystemError("System '{}' is not supported.".format(operating_system))


        def _get_arch():
            \"\"\"Return architecture folder name for current system.\"\"\"
            architecture = _machine_name()
            operating_system = _get_operating_system_name()

            if architecture in {"amd64", "x64", "x86_64", "x86-64", "em64t"}:
                return "x86_64"

            if architecture in {"arm64", "aarch64"} and operating_system == "macos":
                if nuke.NUKE_VERSION_MAJOR >= NUKE_ARM_VERSION:
                    return "aarch64"
                return "x86_64"

            raise UnsupportedSystemError(
                "Architecture '{}' is not supported.".format(architecture),
            )


        def _library_filename():
            \"\"\"Return platform binary filename for the plugin node.\"\"\"
            operating_system = _get_operating_system_name()
            if operating_system == "windows":
                return "{}.dll".format(NODE_CLASS_NAME)
            if operating_system == "linux":
                return "lib{}.so".format(NODE_CLASS_NAME)
            return "lib{}.dylib".format(NODE_CLASS_NAME)


        def _build_plugin_path():
            \"\"\"Build expected plugin path in installed package.\"\"\"
            version_folder = _resolve_version_folder()
            return normalized_path(
                os.path.join(
                    INSTALLATION_PATH,
                    PLUGIN_BIN_DIRECTORY,
                    version_folder,
                    _get_operating_system_name(),
                    _get_arch(),
                )
            )


        def _build_binary_path(plugin_path):
            \"\"\"Build absolute plugin binary path.\"\"\"
            return normalized_path(os.path.join(plugin_path, _library_filename()))


        def _is_minor_version_folder(name):
            \"\"\"Return True for folders in Major.Minor format.\"\"\"
            parts = name.split(".")
            return len(parts) == 2 and all(part.isdigit() for part in parts)


        def _resolve_version_folder():
            \"\"\"Resolve the best available version folder for the running Nuke.\"\"\"
            requested = _get_nuke_version()
            plugin_bin_root = os.path.join(INSTALLATION_PATH, PLUGIN_BIN_DIRECTORY)

            if os.path.isdir(os.path.join(plugin_bin_root, requested)):
                return requested

            if not os.path.isdir(plugin_bin_root):
                return requested

            try:
                available = [
                    entry
                    for entry in os.listdir(plugin_bin_root)
                    if _is_minor_version_folder(entry)
                    and os.path.isdir(os.path.join(plugin_bin_root, entry))
                ]
            except OSError:
                return requested

            try:
                requested_major, requested_minor = (
                    int(part) for part in requested.split(".", 1)
                )
            except ValueError:
                return requested

            same_major = []
            for entry in available:
                major, minor = (int(part) for part in entry.split(".", 1))
                if major == requested_major:
                    same_major.append((minor, entry))

            if not same_major:
                return requested

            lower_or_equal = [entry for minor, entry in same_major if minor <= requested_minor]
            if lower_or_equal:
                selected = max(
                    lower_or_equal,
                    key=lambda version: int(version.split(".", 1)[1]),
                )
            else:
                selected = min(
                    (entry for _, entry in same_major),
                    key=lambda version: int(version.split(".", 1)[1]),
                )

            logger.warning(
                "__NODE_KEY__ binary folder '%s' not found, using '%s' fallback.",
                requested,
                selected,
            )
            return selected


        def _is_plugin_path_registered(plugin_path):
            target = normalized_path(plugin_path)
            try:
                return any(normalized_path(path) == target for path in nuke.pluginPath())
            except Exception:
                return False


        def _is_node_class_available():
            return hasattr(nuke, "nodes") and hasattr(nuke.nodes, NODE_CLASS_NAME)


        def _ensure_plugin_path_registered(plugin_path):
            if _is_plugin_path_registered(plugin_path):
                return
            nuke.pluginAddPath(str(plugin_path))  # ty: ignore[unresolved-attribute]


        def _load_binary(binary_path):
            try:
                nuke.load(binary_path)  # ty: ignore[unresolved-attribute]
            except Exception as error:
                logger.debug("Direct binary load failed for '%s': %s", binary_path, error)
                try:
                    nuke.load(NODE_CLASS_NAME)  # ty: ignore[unresolved-attribute]
                except Exception as fallback_error:
                    raise PluginLoadError(
                        "Unable to load '{}' from '{}': {}".format(
                            NODE_CLASS_NAME,
                            binary_path,
                            fallback_error,
                        ),
                    )

            if not _is_node_class_available():
                raise PluginLoadError(
                    "Binary '{}' loaded but node class '{}' is unavailable.".format(
                        binary_path,
                        NODE_CLASS_NAME,
                    ),
                )


        def ensure_node_class_loaded():
            \"\"\"Ensure plugin path is present and node class is actually loadable.\"\"\"
            plugin_path = _build_plugin_path()
            if not os.path.isdir(plugin_path):
                raise PluginNotFoundError(
                    (
                        "__NODE_KEY__ is installed, but this Nuke version '{}' is not available "
                        "in this package."
                    ).format(nuke.NUKE_VERSION_STRING),
                )

            binary_path = _build_binary_path(plugin_path)
            if not os.path.isfile(binary_path):
                raise PluginNotFoundError(
                    "__NODE_KEY__ binary was not found at '{}'.".format(binary_path)
                )

            _ensure_plugin_path_registered(plugin_path)
            _load_binary(binary_path)
            return plugin_path


        def add_plugin_path():
            \"\"\"Add plugin path to Nuke if found and return the resolved path.\"\"\"
            os.environ[PLUGIN_LOADED_ENV_VAR] = "0"
            os.environ.pop(PLUGIN_BINARY_PATH_ENV_VAR, None)

            plugin_path = ensure_node_class_loaded()
            os.environ[PLUGIN_LOADED_ENV_VAR] = "1"
            os.environ[PLUGIN_BINARY_PATH_ENV_VAR] = plugin_path
            return plugin_path


        def add_plugin_path_safe():
            \"\"\"Add plugin path to Nuke if found, otherwise log failure.\"\"\"
            try:
                plugin_path = add_plugin_path()
                logger.info("__NODE_KEY__ plugin loaded successfully from '%s'.", plugin_path)
                return True
            except (PluginNotFoundError, UnsupportedSystemError, PluginLoadError):
                logger.exception("__NODE_KEY__ plugin loading failed.")
                return False
        """
    )


def render_package_dunder_init() -> str:
    return dedent(
        """
        \"\"\"__NODE_KEY__ package.\"\"\"
        """
    )


def render_workspace_cargo_toml() -> str:
    return dedent(
        """
        [workspace]
        members = [
            "crates/__NODE_CRATE_NAME__",
            "xtask",
        ]
        resolver = "2"
        """
    )


def render_workspace_readme() -> str:
    return dedent(
        """
        # __NODE_KEY__ - work

        Ce dossier est ton loop de dev rapide.

        - `__NODE_KEY__/` : package Nuke local de travail
        - `crates/__NODE_CRATE_NAME__/` : node natif C++/Rust
        - `xtask/` : build helper multi-version Nuke
        - `scripts/runtime_smoke.py` : smoke runtime headless pour la CI

        ## Build local rapide

        ```powershell
        cargo xtask --compile --nuke-versions 16.0 --target-platform windows --output-to-package --limit-threads
        ```

        Sortie attendue:

        `__NODE_KEY__/bin/16.0/windows/x86_64/__NODE_KEY__.dll`

        ## Test local dans Nuke

        1. copier `work/init.py` et `work/__NODE_KEY__/` dans `.nuke`, ou
        2. ajouter temporairement `work/` a `NUKE_PATH`

        Quand le package Python est pret pour une release:

        ```powershell
        python ..\\tools\\sync_package_from_work.py
        ```
        """
    )


def render_dot_nuke_init_example() -> str:
    return dedent(
        """
        # Example `.nuke/init.py`
        import nuke

        nuke.pluginAddPath("./__NODE_KEY__")
        """
    )


def render_crate_cargo_toml() -> str:
    return dedent(
        """
        [package]
        name = "__NODE_CRATE_NAME__"
        version = "__NODE_VERSION__"
        edition = "2024"
        links = "DDImage"
        publish = false

        [lib]
        name = "__NODE_LIB_NAME__"
        crate-type = ["cdylib"]

        [dependencies]

        [build-dependencies]
        cc = "1.2"
        """
    )


def render_crate_build_rs() -> str:
    return dedent(
        """
        use std::path::PathBuf;

        fn main() {
            println!("cargo:rustc-check-cfg=cfg(__NODE_CFG_NAME__)");
            println!("cargo:rerun-if-env-changed=NUKE_SOURCE_PATH");
            println!("cargo:rerun-if-env-changed=PLATFORM_NAME");
            println!("cargo:rerun-if-env-changed=CPP_VERSION");
            println!("cargo:rerun-if-changed=src/__NODE_CPP_FILE__");

            let nuke_root = if let Ok(sources) = std::env::var("NUKE_SOURCE_PATH") {
                PathBuf::from(sources)
            } else {
                println!("cargo:warning=NUKE_SOURCE_PATH not set; skipping native __NODE_KEY__ build.");
                return;
            };
            let nuke_path = nuke_root.join("include");

            let platform_name = if let Ok(name) = std::env::var("PLATFORM_NAME") {
                name
            } else {
                println!("cargo:warning=PLATFORM_NAME not set; skipping native __NODE_KEY__ build.");
                return;
            };

            let cpp_version = std::env::var("CPP_VERSION").unwrap_or_else(|_| "17".to_string());

            let mut builder = cc::Build::new();
            builder
                .cpp(true)
                .std(&format!("c++{cpp_version}"))
                .file("src/__NODE_CPP_FILE__")
                .include(&nuke_path)
                .flag_if_supported("-DGLEW_NO_GLU");

            if platform_name == "windows" {
                builder
                    .define("_CPPUNWIND", "1")
                    .define("NOMINMAX", "1")
                    .define("_USE_MATH_DEFINES", "1")
                    .flag("/EHsc");
            } else if platform_name == "linux" {
                builder
                    .flag("-fPIC")
                    .flag_if_supported("-Wno-deprecated-copy-with-user-provided-copy")
                    .flag_if_supported("-Wno-ignored-qualifiers")
                    .flag_if_supported("-Wno-date-time")
                    .flag_if_supported("-Wno-unused-parameter");

                if std::env::var("USE_CXX11_ABI").is_ok() {
                    builder.flag("-D_GLIBCXX_USE_CXX11_ABI=1");
                }
            } else if platform_name == "macos" {
                builder
                    .flag_if_supported("-Wno-deprecated-copy-with-user-provided-copy")
                    .flag_if_supported("-Wno-ignored-qualifiers")
                    .flag_if_supported("-Wno-date-time")
                    .flag_if_supported("-Wno-unused-parameter");
            }

            builder.compile("__NODE_CRATE_NAME__");
            println!("cargo:rustc-cfg=__NODE_CFG_NAME__");

            println!("cargo:rustc-link-search=all={}", nuke_root.display());
            println!("cargo:rustc-link-lib=dylib=DDImage");
        }
        """
    )


def render_crate_lib_rs() -> str:
    return dedent(
        """
        #[unsafe(no_mangle)]
        pub extern "C" fn __NODE_RUST_LINK_FN__() {
            #[cfg(__NODE_CFG_NAME__)]
            unsafe {
                __NODE_KEEPALIVE_FN__();
            }
        }

        #[cfg(__NODE_CFG_NAME__)]
        unsafe extern "C" {
            fn __NODE_KEEPALIVE_FN__();
        }
        """
    )


def render_cpp_node() -> str:
    return dedent(
        """
        static const char* const CLASS = "__NODE_KEY__";
        static const char* const HELP =
            "__NODE_DESCRIPTION__";

        #include <algorithm>
        #include <cmath>

        #include "DDImage/Iop.h"
        #include "DDImage/Knobs.h"
        #include "DDImage/Row.h"

        using namespace DD::Image;

        namespace {

        inline double clamp_double(double value, double lo, double hi) {
          return std::max(lo, std::min(hi, value));
        }

        class __NODE_KEY__ : public Iop {
         public:
          explicit __NODE_KEY__(Node* node) : Iop(node) {}

          const char* Class() const override { return CLASS; }
          const char* node_help() const override { return HELP; }

          int minimum_inputs() const override { return 1; }
          int maximum_inputs() const override { return 1; }

          void knobs(Knob_Callback f) override {
            Double_knob(f, &gain_, "gain", "gain");
            Tooltip(f, "Simple template knob. Replace this section with your real UI.");

            Double_knob(f, &bias_, "bias", "bias");
            Tooltip(f, "Simple template knob. Replace this section with your real UI.");
          }

          void _validate(bool) override {
            if (!input(0)) {
              info_.channels(Mask_None);
              set_out_channels(Mask_None);
              return;
            }

            copy_info();
            info_.channels(input0().channels());
            set_out_channels(Mask_All);
            info_.black_outside(false);

            gain_ = clamp_double(gain_, -1000.0, 1000.0);
            bias_ = clamp_double(bias_, -1000.0, 1000.0);
          }

          void _request(int x, int y, int r, int t, ChannelMask channels, int count) override {
            if (!input(0)) {
              return;
            }
            input0().request(x, y, r, t, channels, count);
          }

          void engine(int y, int x, int r, ChannelMask channels, Row& row) override {
            if (!input(0) || aborted()) {
              return;
            }

            row.get(input0(), y, x, r, channels);

            foreach (channel, channels) {
              float* output = row.writable(channel);
              if (!output) {
                continue;
              }

              for (int pixel = x; pixel < r; ++pixel) {
                const float value = std::isfinite(static_cast<double>(output[pixel]))
                    ? output[pixel]
                    : 0.0f;
                output[pixel] = static_cast<float>(value * gain_ + bias_);
              }
            }
          }

         private:
          double gain_ = 1.0;
          double bias_ = 0.0;

          static const Iop::Description d;
        };

        static Iop* build(Node* node) { return new __NODE_KEY__(node); }

        const Iop::Description __NODE_KEY__::d(
            CLASS,
            "__NODE_MENU_PATH__/__NODE_KEY__",
            build);

        }  // namespace

        extern "C" void __NODE_KEEPALIVE_FN__() {}
        """
    )


def render_repo_readme() -> str:
    return dedent(
        """
        # __NODE_KEY__

        __NODE_DESCRIPTION__

        Ce repo a ete scaffolded pour coller directement au pipeline de TCollection.

        ## Structure

        ```text
        __NODE_KEY__/
          .github/workflows/    # CI build, runtime smoke, auto-tag
          config/               # versions Nuke supportees
          publish/              # package release final pour les artistes
          tools/                # scripts utilitaires repo
          work/                 # loop de dev rapide locale
          node.json
          node_build_config.json
          VERSION
        ```

        ## Demarrage rapide

        Build Windows / Nuke 16.0:

        ```powershell
        cd work
        cargo xtask --compile --nuke-versions 16.0 --target-platform windows --output-to-package --limit-threads
        ```

        Sortie attendue:

        `work/__NODE_KEY__/bin/16.0/windows/x86_64/__NODE_KEY__.dll`

        ## Sync du package release

        Quand le package Python de `work/__NODE_KEY__/` est bon:

        ```powershell
        python tools/sync_package_from_work.py
        ```

        Ce script resynchronise `publish/__NODE_KEY__/` sans ecraser `publish/__NODE_KEY__/bin/`.

        ## Release node

        1. verifier le package localement dans Nuke
        2. lancer `python tools/sync_package_from_work.py`
        3. bump `VERSION`
        4. pousser sur `main`
        5. laisser GitHub Actions tagger `vX.Y.Z` et publier le zip
        """
    )


def render_contributing() -> str:
    return dedent(
        """
        # Contributing

        Ce repo suit un workflow simple pour garder les nodes coherents avec TCollection.

        ## Branches

        - `main`: code livrable uniquement
        - `feat/*`, `fix/*`, `chore/*`: branches courtes par changement
        - `release/vX.Y.Z`: optionnel si tu veux une phase de stabilisation

        Evite une branche `work` permanente. Pour bosser sur plusieurs taches en
        parallele, prefere plusieurs `git worktree`.

        ## Versioning

        - `VERSION` est la source de verite et doit etre en SemVer `X.Y.Z`
        - sur push vers `main`, si `VERSION` change, GitHub Actions cree le tag `vX.Y.Z`

        ## Release standard

        1. creer une branche courte
        2. iterer localement dans `work/`
        3. sync package avec `python tools/sync_package_from_work.py`
        4. bump `VERSION`
        5. merger sur `main`
        6. laisser la CI publier la release
        """
    )


def render_ci_testing(backend_mode: str) -> str:
    return dedent(
        f"""
        # CI Testing

        Ce repo utilise 2 niveaux de validation:

        1. build/package sur runners GitHub-hosted
        2. smoke runtime sur runners self-hosted avec Nuke installe

        ## Profil actuel

        - backend: {backend_mode}
        - package source: `publish/`
        - loop locale rapide: `work/`

        ## Build CI GitHub-hosted

        Workflow:

        - `.github/workflows/nuke-build.yml`

        Ce workflow:

        - lit les versions supportees dans `config/nuke_versions.json`
        - compile le plugin natif
        - reconstruit le package final depuis `publish/`
        - verifie le loader package avec `work/scripts/validate_package_import.py`

        ## Runtime smoke self-hosted

        Workflow:

        - `.github/workflows/nuke-runtime-smoke.yml`

        Ce workflow:

        - lance un vrai executable Nuke
        - charge le plugin depuis `publish/`
        - cree le node
        - execute une frame
        """
    )


def render_changelog(version: str) -> str:
    return dedent(
        f"""
        # Changelog

        ## {version}

        - initial scaffold
        """
    )


def render_sync_package_script() -> str:
    return dedent(
        """
        #!/usr/bin/env python3
        \"\"\"Mirror work/__NODE_KEY__ into publish/__NODE_KEY__ for release packaging.\"\"\"

        from __future__ import annotations

        import shutil
        from pathlib import Path

        ROOT = Path(__file__).resolve().parents[1]
        SOURCE = ROOT / "work" / "__NODE_KEY__"
        TARGET = ROOT / "publish" / "__NODE_KEY__"
        SKIP_SOURCE_NAMES = {"bin", "__pycache__", ".DS_Store"}


        def remove_path(path: Path) -> None:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


        def copy_path(source: Path, target: Path) -> None:
            if source.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(
                    source,
                    target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                )
                return

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


        def main() -> int:
            if not SOURCE.is_dir():
                raise SystemExit(f"Missing source package: {SOURCE}")

            TARGET.mkdir(parents=True, exist_ok=True)

            source_names = {
                path.name
                for path in SOURCE.iterdir()
                if path.name not in SKIP_SOURCE_NAMES
            }
            for target_child in list(TARGET.iterdir()):
                if target_child.name == "bin":
                    continue
                if target_child.name == "__pycache__":
                    remove_path(target_child)
                    continue
                if target_child.name not in source_names:
                    remove_path(target_child)

            for source_child in SOURCE.iterdir():
                if source_child.name in SKIP_SOURCE_NAMES:
                    continue
                copy_path(source_child, TARGET / source_child.name)

            print(f"Synced {SOURCE} -> {TARGET}")
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )


def build_generated_root_files(args: argparse.Namespace, backend_mode: str) -> dict[Path, str]:
    return {
        Path("VERSION"): "__NODE_VERSION__",
        Path("CHANGELOG.md"): render_changelog(args.version),
        Path("README.md"): render_repo_readme(),
        Path("CONTRIBUTING.md"): render_contributing(),
        Path("CI_TESTING.md"): render_ci_testing(backend_mode),
        Path("publish/init.py"): render_root_init(),
        Path("work/init.py"): render_root_init(),
        Path("work/Cargo.toml"): render_workspace_cargo_toml(),
        Path("work/README.md"): render_workspace_readme(),
        Path("work/dot_nuke_init_example.py"): render_dot_nuke_init_example(),
        Path("tools/sync_package_from_work.py"): render_sync_package_script(),
    }


def build_generated_package_files() -> dict[str, str]:
    return {
        "__init__.py": render_package_dunder_init(),
        "init.py": render_package_init(),
        "menu.py": render_package_menu(),
        "_consts.py": render_package_consts(),
        "_credits_link.py": render_package_credits_link(),
        "_menu_creator.py": render_package_menu_creator(),
        "_plugin_loader.py": render_package_plugin_loader(),
    }


def create_generated_files(
    output_root: Path,
    args: argparse.Namespace,
    mapping: dict[str, str],
    backend_mode: str,
    node_build_config: dict[str, object],
) -> None:
    for relative_path, raw_contents in build_generated_root_files(args, backend_mode).items():
        write_text(output_root / relative_path, replace_tokens(raw_contents, mapping))

    package_files = build_generated_package_files()
    for package_root_name in ("publish", "work"):
        package_root = output_root / package_root_name / mapping["__NODE_KEY__"]
        for relative_name, raw_contents in package_files.items():
            write_text(package_root / relative_name, replace_tokens(raw_contents, mapping))

        (package_root / "bin").mkdir(parents=True, exist_ok=True)
        write_text(package_root / "bin" / ".gitkeep", "")
        (package_root / "resources").mkdir(parents=True, exist_ok=True)
        write_text(package_root / "resources" / ".gitkeep", "")

    crate_root = output_root / "work" / "crates" / mapping["__NODE_CRATE_NAME__"]
    write_text(crate_root / "Cargo.toml", replace_tokens(render_crate_cargo_toml(), mapping))
    write_text(crate_root / "build.rs", replace_tokens(render_crate_build_rs(), mapping))
    write_text(crate_root / "src" / "lib.rs", replace_tokens(render_crate_lib_rs(), mapping))
    write_text(
        crate_root / "src" / mapping["__NODE_CPP_FILE__"],
        replace_tokens(render_cpp_node(), mapping),
    )

    node_payload = {
        "key": args.node_key,
        "label": args.node_key,
        "version": args.version,
        "status": args.status,
        "class_name": args.node_key,
        "bootstrap_module": f"{args.node_key}.init",
        "python_path": "publish",
        "work_path": "work",
        "publish_path": "publish",
        "notes": "",
    }
    write_json(output_root / "node.json", node_payload)

    build_section = dict(node_build_config.get("build", {}))
    build_section["work_root"] = "work"
    build_section["package_dir"] = f"work/{args.node_key}"
    build_section["versions_config"] = "config/nuke_versions.json"

    node_build_payload = {
        "node": {
            "class_name": args.node_key,
            "type": args.node_type,
            "version": args.version,
            "vendor": args.vendor,
        },
        "build": build_section,
    }
    write_json(output_root / "node_build_config.json", node_build_payload)


def replace_seed_tokens_in_text_files(
    output_root: Path,
    seed_mapping: dict[str, str],
    target_mapping: dict[str, str],
    vendor: str,
    vendor_url: str,
) -> None:
    replacements = {
        seed_mapping["key"]: target_mapping["key"],
        seed_mapping["lower"]: target_mapping["lower"],
        seed_mapping["snake"]: target_mapping["snake"],
        seed_mapping["env"]: target_mapping["env"],
        "Thomas Petroni": vendor,
        "https://www.linkedin.com/in/thomas-petroni/": vendor_url,
    }

    for path in output_root.rglob("*"):
        if not path.is_file() or not is_text_file(path):
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = original
        for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8")


def rename_paths(output_root: Path, seed_mapping: dict[str, str], target_mapping: dict[str, str]) -> None:
    replacements = {
        seed_mapping["key"]: target_mapping["key"],
        seed_mapping["lower"]: target_mapping["lower"],
        seed_mapping["snake"]: target_mapping["snake"],
    }
    for path in sorted(output_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        for old, new in replacements.items():
            if old in path.name:
                path.rename(path.with_name(path.name.replace(old, new)))
                break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a new TCollection native node repository.")
    parser.add_argument("node_key", help="Node class/key, for example TEdgeDetect")
    parser.add_argument(
        "--output",
        default="",
        help="Output repository path. Defaults to the sibling folder ../<NodeKey>.",
    )
    parser.add_argument(
        "--template-source",
        default=str(DEFAULT_TEMPLATE_SOURCE),
        help="CPU-native seed repo used for workflows/xtask defaults.",
    )
    parser.add_argument("--vendor", default="Thomas Petroni", help="Vendor name shown in metadata.")
    parser.add_argument(
        "--vendor-url",
        default="https://www.linkedin.com/in/thomas-petroni/",
        help="Vendor URL used by the credits helper.",
    )
    parser.add_argument("--status", default="test", help="Initial node status (stable/test/hold).")
    parser.add_argument("--version", default="0.1.0", help="Initial node version.")
    parser.add_argument(
        "--description",
        default="TCollection native node scaffold. Replace this example processing with your real node.",
        help="Short description/help string.",
    )
    parser.add_argument(
        "--menu-path",
        default="Filter",
        help="Nuke menu path prefix used in the node description.",
    )
    parser.add_argument(
        "--node-type",
        default="Iop",
        help="Value written to node_build_config.json (for example Iop or IopFilter).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output directory if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_args(args)

    seed_root = Path(args.template_source).resolve()
    if not seed_root.is_dir():
        die(f"Template source does not exist: {seed_root}")

    output_root = Path(args.output).resolve() if args.output else (ROOT.parent / args.node_key).resolve()

    seed_node_key = read_seed_node_key(seed_root)
    seed_variants = build_name_variants(seed_node_key)
    target_variants = build_name_variants(args.node_key)

    if output_root.exists():
        if not args.force:
            die(f"Output path already exists: {output_root}\nUse --force to replace it.")
        shutil.rmtree(output_root)

    seed_build_config = read_seed_build_config(seed_root)
    backend_mode = str(seed_build_config.get("build", {}).get("backend_mode", "CPU")).strip() or "CPU"
    if backend_mode != "CPU":
        die(
            "This scaffold currently targets the CPU-native baseline.\n"
            f"Template source '{seed_root}' reports backend_mode={backend_mode!r}.\n"
            "Use a CPU seed repo such as TColorRamp for now."
        )

    output_root.mkdir(parents=True, exist_ok=True)
    copy_seed_paths(seed_root, output_root)

    rename_paths(output_root, seed_variants, target_variants)
    replace_seed_tokens_in_text_files(
        output_root,
        seed_mapping=seed_variants,
        target_mapping=target_variants,
        vendor=args.vendor,
        vendor_url=args.vendor_url,
    )

    placeholder_mapping = {
        "__NODE_KEY__": args.node_key,
        "__NODE_LOWER__": target_variants["lower"],
        "__NODE_SNAKE__": target_variants["snake"],
        "__NODE_ENV__": target_variants["env"],
        "__NODE_VERSION__": args.version,
        "__NODE_STATUS__": args.status,
        "__NODE_VENDOR__": args.vendor,
        "__NODE_VENDOR_URL__": args.vendor_url,
        "__NODE_DESCRIPTION__": args.description,
        "__NODE_MENU_PATH__": args.menu_path,
        "__NODE_TYPE__": args.node_type,
        "__NODE_CRATE_NAME__": target_variants["crate_name"],
        "__NODE_LIB_NAME__": target_variants["lib_name"],
        "__NODE_CFG_NAME__": target_variants["cfg_name"],
        "__NODE_CPP_FILE__": target_variants["cpp_file"],
        "__NODE_RUST_LINK_FN__": target_variants["rust_link_fn"],
        "__NODE_KEEPALIVE_FN__": target_variants["keepalive_fn"],
    }

    create_generated_files(
        output_root=output_root,
        args=args,
        mapping=placeholder_mapping,
        backend_mode=backend_mode,
        node_build_config=seed_build_config,
    )

    print(f"Scaffold created at: {output_root}")
    print("Next steps:")
    print(f"  1. cd {output_root}")
    print("  2. cd work")
    print("  3. cargo xtask --compile --nuke-versions 16.0 --target-platform windows --output-to-package --limit-threads")
    print("  4. test in Nuke from work/")
    print("  5. python tools/sync_package_from_work.py before the first release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
