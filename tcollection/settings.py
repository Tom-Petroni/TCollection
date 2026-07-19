"""TCollection settings dialog with a portfolio-inspired web UI."""

from __future__ import annotations

import base64
import html
import json
import mimetypes
from pathlib import Path
from typing import Any

import nuke  # ty: ignore[unresolved-import]

from .loader import get_collection_info, get_nodes, resolve_node_icon_path
from .updater import check_for_updates, get_install_state, prepare_update_for_next_launch

try:  # pragma: no cover - depends on the Nuke runtime
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]

    _QT_API = "PySide2"
except Exception:  # pragma: no cover - fallback for newer runtimes
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]

    _QT_API = "PySide6"

try:  # pragma: no cover - optional dependency in Nuke
    if _QT_API == "PySide2":
        from PySide2.QtWebChannel import QWebChannel  # type: ignore[import-not-found]
        from PySide2.QtWebEngineWidgets import QWebEngineView  # type: ignore[import-not-found]
    else:
        from PySide6.QtWebChannel import QWebChannel  # type: ignore[import-not-found]
        from PySide6.QtWebEngineWidgets import QWebEngineView  # type: ignore[import-not-found]

    _HAS_WEB_ENGINE = True
except Exception:  # pragma: no cover - widget fallback is used instead
    QWebChannel = None  # type: ignore[assignment]
    QWebEngineView = None  # type: ignore[assignment]
    _HAS_WEB_ENGINE = False


ROOT_DIR = Path(__file__).resolve().parents[1]
_SETTINGS_DIALOG: "TCollectionSettingsDialog | None" = None
_NODE_DESCRIPTIONS = {
    "TNoise": "2D/3D procedural noise creation for lookdev and technical maps.",
    "TBlur": "Art-directable blur tool for softening images while preserving usable detail.",
    "TMask": "Procedural masking node for fast texture, edge and volume isolation.",
    "TColorRamp": "Color ramp node for remapping values with clean gradient control.",
    "TVectorBlur": "CUDA vector blur node with mask and warp controls for motion/vector passes.",
}


def _normalize_status(status: str) -> str:
    value = status.strip().lower()
    return value or "unknown"


def _status_meta(status: str) -> dict[str, str]:
    normalized = _normalize_status(status)
    if normalized == "stable":
        return {
            "key": normalized,
            "label": "Stable",
            "accent": "#9ce2b0",
            "surface": "#1f3a27",
            "border": "rgba(156, 226, 176, 0.22)",
        }
    if normalized == "test":
        return {
            "key": normalized,
            "label": "Test",
            "accent": "#f4d18f",
            "surface": "#47371d",
            "border": "rgba(244, 209, 143, 0.22)",
        }
    if normalized == "hold":
        return {
            "key": normalized,
            "label": "Hold",
            "accent": "#dfbbe6",
            "surface": "#3b2d42",
            "border": "rgba(223, 187, 230, 0.22)",
        }
    if normalized == "package":
        return {
            "key": normalized,
            "label": "Package",
            "accent": "#a8c7fa",
            "surface": "#243347",
            "border": "rgba(168, 199, 250, 0.22)",
        }
    return {
        "key": normalized,
        "label": normalized.title(),
        "accent": "#bdc6cf",
        "surface": "#25303c",
        "border": "rgba(189, 198, 207, 0.22)",
    }


def _status_sort_value(status: str) -> int:
    normalized = _normalize_status(status)
    if normalized == "stable":
        return 0
    if normalized == "test":
        return 1
    if normalized == "hold":
        return 2
    return 3


def _iter_runtime_files(root_name: str) -> list[Path]:
    root = ROOT_DIR / root_name
    if not root.is_dir():
        return []

    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() == "readme.md":
            continue
        files.append(path)
    return files


def _asset_initials(name: str) -> str:
    tokens = [character for character in name if character.isalnum()]
    if not tokens:
        return "TC"
    return "".join(tokens[:2]).upper()


def _path_to_data_url(path_str: str) -> str:
    if not path_str:
        return ""

    path = Path(path_str)
    if not path.is_file():
        return ""

    mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:{mime_type};base64,{encoded}"


def _safe_url(url: str) -> str:
    value = url.strip()
    if value.startswith("https://") or value.startswith("http://"):
        return value
    return ""


def _svg_data_url(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _generated_node_icon_data(node_key: str) -> str:
    normalized = node_key.strip()
    if normalized == "TColorRamp":
        return _svg_data_url(
            """
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="ramp" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0ea5e9"/>
      <stop offset="33%" stop-color="#8b5cf6"/>
      <stop offset="66%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#ef4444"/>
    </linearGradient>
  </defs>
  <rect x="6" y="22" width="52" height="20" rx="10" fill="url(#ramp)"/>
</svg>
""".strip()
        )
    return ""


class TCollectionBridge(QtCore.QObject):
    """Qt bridge exposed to the embedded web page."""

    def __init__(self, dialog: "TCollectionSettingsDialog") -> None:
        super().__init__(dialog)
        self._dialog = dialog

    @QtCore.Slot(result=str)
    def getState(self) -> str:
        return self._dialog._state_json()

    @QtCore.Slot(result=str)
    def checkUpdates(self) -> str:
        self._dialog._run_update_check()
        return self._dialog._state_json()

    @QtCore.Slot(result=str)
    def installUpdate(self) -> str:
        self._dialog._run_update_prepare()
        return self._dialog._state_json()

    @QtCore.Slot(result=str)
    def openReleaseNotes(self) -> str:
        self._dialog._open_release_notes()
        return self._dialog._state_json()

    @QtCore.Slot(str, result=bool)
    def openExternalUrl(self, url: str) -> bool:
        return self._dialog._open_external_url(url)

    @QtCore.Slot()
    def closeWindow(self) -> None:
        self._dialog.close()


class TCollectionSettingsDialog(QtWidgets.QDialog):
    """Collection settings dialog."""

    def __init__(self) -> None:
        super().__init__()
        self._update_result: dict[str, Any] | None = None
        self._banner_message = ""
        self._banner_tone = "info"
        self._web_view: Any = None
        self._text_view: Any = None
        self._check_button: Any = None
        self._prepare_button: Any = None
        self._notes_button: Any = None
        self._summary_label: Any = None

        self.setWindowTitle("TCollection Settings")
        self.setObjectName("TCollectionSettingsDialog")
        self.setMinimumSize(1120, 860)
        self.setModal(False)

        if _HAS_WEB_ENGINE:
            self._build_web_ui()
        else:
            self._build_widget_fallback()

        self.refresh_all()

    def _build_web_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setStyleSheet("QDialog#TCollectionSettingsDialog { background: #131314; }")

        self._web_view = QWebEngineView(self)
        try:
            self._web_view.page().setBackgroundColor(QtGui.QColor("#131314"))
        except Exception:
            pass

        channel = QWebChannel(self._web_view.page())
        bridge = TCollectionBridge(self)
        channel.registerObject("tcollectionBridge", bridge)
        self._web_view.page().setWebChannel(channel)

        self._web_channel = channel
        self._web_bridge = bridge
        layout.addWidget(self._web_view)

    def _build_widget_fallback(self) -> None:
        self.setStyleSheet(
            """
            QDialog#TCollectionSettingsDialog {
                background: #0a0a0a;
                color: #f5f5f5;
                font-family: "DM Sans", "Segoe UI", sans-serif;
            }
            QLabel#Title {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 34px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#Body {
                color: #c4c7c5;
                font-size: 13px;
                line-height: 1.6;
            }
            QTextBrowser {
                background: #1e1f20;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 28px;
                color: #e3e3e3;
                padding: 10px;
            }
            QPushButton {
                background: #282a2c;
                color: #e3e3e3;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
                padding: 10px 16px;
                font-size: 12px;
            }
            QPushButton#Primary {
                background: #a8c7fa;
                color: #131314;
                border-color: transparent;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #333537;
            }
            QPushButton#Primary:hover {
                background: #d3e3fd;
            }
            """
        )

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.setSpacing(18)

        title = QtWidgets.QLabel("TCollection")
        title.setObjectName("Title")
        title.setAlignment(QtCore.Qt.AlignCenter)
        outer.addWidget(title)

        self._summary_label = QtWidgets.QLabel("")
        self._summary_label.setObjectName("Body")
        self._summary_label.setWordWrap(True)
        self._summary_label.setAlignment(QtCore.Qt.AlignCenter)
        outer.addWidget(self._summary_label)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)

        self._check_button = QtWidgets.QPushButton("Check Updates")
        self._check_button.setObjectName("Primary")
        self._check_button.clicked.connect(self._run_update_check)
        buttons.addWidget(self._check_button)

        self._prepare_button = QtWidgets.QPushButton("Install for Next Launch")
        self._prepare_button.clicked.connect(self._run_update_prepare)
        buttons.addWidget(self._prepare_button)

        self._notes_button = QtWidgets.QPushButton("Release Notes")
        self._notes_button.clicked.connect(self._open_release_notes)
        buttons.addWidget(self._notes_button)

        buttons.addStretch(1)
        outer.addLayout(buttons)

        self._text_view = QtWidgets.QTextBrowser()
        self._text_view.setOpenExternalLinks(True)
        outer.addWidget(self._text_view, 1)

    def _build_node_assets(self) -> list[dict[str, Any]]:
        node_assets: list[dict[str, Any]] = []
        nodes = sorted(
            [entry for entry in get_nodes() if str(entry.get("class_name", "")).strip()],
            key=lambda entry: (
                _status_sort_value(str(entry.get("status", ""))),
                str(entry.get("label", entry.get("key", ""))).lower(),
            ),
        )

        for entry in nodes:
            node_key = str(entry.get("key", "")).strip()
            label = str(entry.get("label", node_key)).strip() or node_key
            status_meta = _status_meta(str(entry.get("status", "")))
            source = entry.get("source", {})
            if not isinstance(source, dict):
                source = {}
            icon_data_url = _path_to_data_url(resolve_node_icon_path(node_key)) or _generated_node_icon_data(node_key)
            description = _NODE_DESCRIPTIONS.get(node_key, str(entry.get("notes", "")).strip() or "Node runtime")

            node_assets.append(
                {
                    "id": f"node:{node_key}",
                    "title": label,
                    "kind": "Node",
                    "version": str(entry.get("version", "")).strip() or "n/a",
                    "status": status_meta["key"],
                    "status_label": status_meta["label"],
                    "status_accent": status_meta["accent"],
                    "status_surface": status_meta["surface"],
                    "status_border": status_meta["border"],
                    "subtitle": description,
                    "notes": str(entry.get("notes", "")).strip() or "No extra notes yet.",
                    "initials": _asset_initials(label),
                    "icon_data_url": icon_data_url,
                    "relative_path": str(entry.get("python_path", "")).strip(),
                    "repo_url": _safe_url(str(source.get("repo_url", "")).strip()),
                    "releases_url": _safe_url(str(source.get("releases_url", "")).strip()),
                    "source_repo": str(source.get("repo", "")).strip(),
                }
            )

        return node_assets

    def _build_runtime_assets(self, root_name: str, kind: str) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        for path in _iter_runtime_files(root_name):
            status_meta = _status_meta("package")
            assets.append(
                {
                    "id": f"{kind.lower()}:{path.relative_to(ROOT_DIR).as_posix()}",
                    "title": path.stem,
                    "kind": kind,
                    "version": path.suffix.lower().lstrip(".") or "file",
                    "status": status_meta["key"],
                    "status_label": status_meta["label"],
                    "status_accent": status_meta["accent"],
                    "status_surface": status_meta["surface"],
                    "status_border": status_meta["border"],
                    "subtitle": f"{kind} asset",
                    "notes": path.relative_to(ROOT_DIR).as_posix(),
                    "initials": _asset_initials(path.stem),
                    "icon_data_url": "",
                    "relative_path": path.relative_to(ROOT_DIR).as_posix(),
                    "repo_url": "",
                    "releases_url": "",
                    "source_repo": "",
                }
            )
        return assets

    def _build_sections(self) -> list[dict[str, Any]]:
        nodes = self._build_node_assets()
        gizmos = self._build_runtime_assets("gizmos", "Gizmo")
        scripts = self._build_runtime_assets("scripts", "Script")

        return [
            {
                "title": "Nodes",
                "description": "Production nodes currently tracked by the collection package.",
                "items": nodes,
            },
            {
                "title": "Gizmos",
                "description": "Reusable gizmos shipped with the current install.",
                "items": gizmos,
            },
            {
                "title": "Scripts",
                "description": "Utility scripts available alongside the collection runtime.",
                "items": scripts,
            },
        ]

    def _build_state(self) -> dict[str, Any]:
        info = get_collection_info()
        install_state = get_install_state()
        sections = self._build_sections()

        current_version = str(info.get("version", "unknown")).strip()
        managed_version = install_state.get("current_version", "") or current_version
        pending_version = install_state.get("pending_version", "")
        links = info.get("links", {})
        if not isinstance(links, dict):
            links = {}

        if self._update_result is None:
            latest_version = current_version
            update_available = False
            update_summary = ""
            notes_url = _safe_url(str(links.get("releases_url", "")).strip())
            channel = "stable"
        else:
            update_available = bool(self._update_result.get("available", False))
            latest_version = (
                str(self._update_result.get("latest_version", "")).strip() or current_version
            )
            notes_url = _safe_url(str(self._update_result.get("notes_url", "")).strip())
            channel = str(self._update_result.get("channel", "")).strip() or "stable"
            reason = str(self._update_result.get("reason", "")).strip()
            if update_available:
                update_summary = (
                    f"TCollection {latest_version} is available. You are currently on {managed_version}. {reason}"
                )
            else:
                update_summary = (
                    f"TCollection {managed_version} already matches the latest published release. {reason}"
                )

        if pending_version:
            update_summary = (
                f"TCollection {pending_version} has already been prepared for the next Nuke launch. Restart Nuke to activate it."
            )

        node_count = len(sections[0]["items"])
        gizmo_count = len(sections[1]["items"])
        script_count = len(sections[2]["items"])

        install_enabled = update_available and (pending_version != latest_version)
        install_label = "Install Update"
        if pending_version and pending_version == latest_version:
            install_label = "Ready on Next Launch"

        return {
            "collection": {
                "display_name": str(info.get("display_name", "TCollection")).strip() or "TCollection",
                "version": current_version,
                "status": str(info.get("status", "")).strip() or "planning",
                "repo_url": _safe_url(str(links.get("repo_url", "")).strip()),
                "releases_url": _safe_url(str(links.get("releases_url", "")).strip()),
            },
            "header": {
                "kicker": "",
                "subtitle": "Developed by Thomas Petroni",
                "description": "",
                "hero_pill": "Portfolio-inspired collection settings",
            },
            "updates": {
                "summary": update_summary,
                "channel": channel,
                "latest_version": latest_version,
                "managed_version": managed_version,
                "pending_version": pending_version or "None",
                "runtime_root": install_state.get("runtime_root", ""),
                "managed_root": install_state.get("managed_root", ""),
                "versions_root": install_state.get("versions_root", ""),
                "update_available": update_available,
                "install_enabled": install_enabled,
                "install_label": install_label,
                "notes_url": notes_url,
            },
            "stats": [
                {
                    "label": "Collection Version",
                    "value": current_version,
                    "note": "Package currently loaded in Nuke.",
                },
                {
                    "label": "Managed Version",
                    "value": managed_version,
                    "note": "Active version tracked in the managed install root.",
                },
                {
                    "label": "Pending Version",
                    "value": pending_version or "None",
                    "note": "Version that activates after a Nuke restart.",
                },
                {
                    "label": "Latest Release",
                    "value": latest_version,
                    "note": "Most recent GitHub release seen by the updater.",
                },
                {
                    "label": "Nodes",
                    "value": str(node_count),
                    "note": "Node entries listed in the collection manifest.",
                },
                {
                    "label": "Gizmos",
                    "value": str(gizmo_count),
                    "note": "Standalone gizmo files currently packaged.",
                },
                {
                    "label": "Scripts",
                    "value": str(script_count),
                    "note": "Utility scripts currently packaged.",
                },
            ],
            "sections": sections,
            "banner": {
                "message": self._banner_message,
                "tone": self._banner_tone,
            },
            "web_engine": _HAS_WEB_ENGINE,
        }

    def _state_json(self) -> str:
        return json.dumps(self._build_state(), ensure_ascii=False).replace("</", "<\\/")

    def _render_web_ui(self) -> None:
        if self._web_view is None:
            return

        html_text = self._html_template().replace("__TCOLLECTION_STATE__", self._state_json())
        base_url = QtCore.QUrl.fromLocalFile(str(ROOT_DIR).replace("\\", "/") + "/")
        self._web_view.setHtml(html_text, base_url)

    def _render_widget_fallback(self) -> None:
        if self._text_view is None or self._summary_label is None:
            return

        state = self._build_state()
        updates = state["updates"]
        banner = state["banner"]

        summary = updates["summary"]
        if banner["message"]:
            summary = f"{banner['message']}\n\n{summary}"
        self._summary_label.setText(summary)

        self._prepare_button.setEnabled(bool(updates["install_enabled"]))
        self._prepare_button.setText(str(updates.get("install_label", "Install Update")))
        self._notes_button.setEnabled(bool(updates["notes_url"]))

        sections_html: list[str] = []
        for section in state["sections"]:
            items = section["items"]
            items_html = ""
            if not items:
                items_html = "<p style='color:#9aa0a6;'>Nothing packaged in this section yet.</p>"
            else:
                parts = []
                for item in items:
                    links: list[str] = []
                    if item["repo_url"]:
                        links.append(f"<a href='{html.escape(item['repo_url'])}'>Repository</a>")
                    if item["releases_url"]:
                        links.append(f"<a href='{html.escape(item['releases_url'])}'>Releases</a>")
                    links_html = " · ".join(links)
                    if links_html:
                        links_html = f"<div style='margin-top:6px;color:#a8c7fa;'>{links_html}</div>"

                    parts.append(
                        "<div style='padding:16px 18px;margin-top:12px;background:#282a2c;"
                        "border:1px solid rgba(255,255,255,0.08);border-radius:22px;'>"
                        f"<div style='display:flex;justify-content:space-between;gap:12px;align-items:flex-start;'>"
                        f"<div><div style='font-size:17px;color:#ffffff;font-weight:600;'>{html.escape(item['title'])}</div>"
                        f"<div style='margin-top:4px;color:#c4c7c5;font-size:12px;'>{html.escape(item['subtitle'])}</div>"
                        f"<div style='margin-top:8px;color:#9aa0a6;font-size:12px;line-height:1.6;'>{html.escape(item['notes'])}</div>"
                        f"{links_html}</div>"
                        f"<div style='white-space:nowrap;color:{item['status_accent']};font-size:12px;'>{html.escape(item['version'])}</div>"
                        "</div></div>"
                    )
                items_html = "".join(parts)

            sections_html.append(
                "<section style='margin-top:28px;'>"
                f"<h2 style='font-family:Manrope,Segoe UI,sans-serif;font-size:24px;color:#ffffff;'>{html.escape(section['title'])}</h2>"
                f"<p style='color:#c4c7c5;font-size:13px;line-height:1.6;'>{html.escape(section['description'])}</p>"
                f"{items_html}</section>"
            )

        banner_html = ""
        if banner["message"]:
            tone_bg = "#243347" if banner["tone"] != "error" else "#4a2326"
            tone_fg = "#a8c7fa" if banner["tone"] != "error" else "#f2b8b5"
            banner_html = (
                f"<div style='margin-bottom:18px;padding:14px 18px;border-radius:18px;background:{tone_bg};"
                f"color:{tone_fg};font-size:13px;'>{html.escape(banner['message'])}</div>"
            )

        html_output = (
            "<html><body style='background:#131314;color:#e3e3e3;font-family:DM Sans,Segoe UI,sans-serif;"
            "padding:22px;line-height:1.6;'>"
            f"{banner_html}"
            "<h2 style='font-family:Manrope,Segoe UI,sans-serif;font-size:28px;color:#ffffff;margin:0 0 8px;'>Updates</h2>"
            f"<p style='color:#c4c7c5;font-size:13px;'>{html.escape(updates['summary'])}</p>"
            "<ul style='color:#9aa0a6;font-size:12px;'>"
            f"<li>Latest: {html.escape(updates['latest_version'])}</li>"
            f"<li>Installed: {html.escape(updates['managed_version'])}</li>"
            f"<li>Pending: {html.escape(updates['pending_version'])}</li>"
            "</ul>"
            + "".join(sections_html)
            + "</body></html>"
        )
        self._text_view.setHtml(html_output)

    def refresh_all(self) -> None:
        if self._web_view is not None:
            self._render_web_ui()
        else:
            self._render_widget_fallback()

    def _run_update_check(self) -> None:
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self._update_result = check_for_updates()
            current_version = str(get_collection_info().get("version", "unknown")).strip()
            latest_version = str(self._update_result.get("latest_version", "")).strip() or current_version
            if bool(self._update_result.get("available", False)):
                self._banner_message = (
                    f"Update found: TCollection {current_version} -> {latest_version}."
                )
            else:
                self._banner_message = f"TCollection {latest_version} is already up to date."
            self._banner_tone = "info"
        except Exception as exc:
            current_version = str(get_collection_info().get("version", "unknown")).strip()
            self._update_result = {
                "available": False,
                "current_version": current_version,
                "latest_version": current_version,
                "channel": "stable",
                "reason": f"Failed to check updates: {exc}",
                "notes_url": "",
            }
            self._banner_message = f"Update check failed: {exc}"
            self._banner_tone = "error"
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self.refresh_all()

    def _run_update_prepare(self) -> None:
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            result = prepare_update_for_next_launch(self._update_result)
        except Exception as exc:
            self._banner_message = f"Unable to prepare the update: {exc}"
            self._banner_tone = "error"
            self.refresh_all()
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self._banner_message = (
            f"TCollection {result['version']} has been downloaded. Restart Nuke to activate it."
        )
        self._banner_tone = "info"
        self.refresh_all()

    def _open_release_notes(self) -> None:
        if self._update_result is not None:
            notes_url = _safe_url(str(self._update_result.get("notes_url", "")).strip())
            if notes_url:
                self._open_external_url(notes_url)
                return

        links = get_collection_info().get("links", {})
        if not isinstance(links, dict):
            links = {}
        releases_url = _safe_url(str(links.get("releases_url", "")).strip())
        if releases_url:
            self._open_external_url(releases_url)

    def _open_external_url(self, url: str) -> bool:
        safe_url = _safe_url(url)
        if not safe_url:
            return False
        return bool(QtGui.QDesktopServices.openUrl(QtCore.QUrl(safe_url)))

    def _html_template(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TCollection</title>
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
  <style>
    @import url("https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Manrope:wght@500;600;700&display=swap");

    :root {
      --bg: #0a0a0a;
      --surface: rgba(30, 31, 32, 0.92);
      --surface-hover: rgba(40, 42, 44, 0.98);
      --line: rgba(255, 255, 255, 0.08);
      --line-soft: rgba(255, 255, 255, 0.05);
      --text: #f5f5f5;
      --text-soft: #c4c7c5;
      --text-muted: #8e918f;
      --primary: #a8c7fa;
      --primary-strong: #d3e3fd;
      --danger: #f2b8b5;
      --shadow: 0 18px 46px rgba(0, 0, 0, 0.24);
      --radius-xl: 34px;
      --radius-lg: 28px;
      --radius-pill: 999px;
    }

    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; }
    body {
      background:
        radial-gradient(circle at top, rgba(168, 199, 250, 0.07), transparent 30%),
        linear-gradient(180deg, #101112 0%, var(--bg) 100%);
      color: var(--text);
      font-family: "DM Sans", "Segoe UI", sans-serif;
      overflow-y: auto;
      user-select: none;
    }

    body::-webkit-scrollbar { width: 10px; }
    body::-webkit-scrollbar-track { background: transparent; }
    body::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.12);
      border-radius: 999px;
    }

    .page-shell {
      width: min(100%, 940px);
      margin: 0 auto;
      padding: 42px 24px 36px;
    }

    .hero {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 14px;
      text-align: center;
      margin-bottom: 28px;
    }

    .hero-kicker,
    .section-kicker {
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: rgba(163, 163, 163, 0.9);
    }

    .hero-title {
      margin: 0;
      font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
      font-size: clamp(42px, 7vw, 68px);
      line-height: 0.95;
      font-weight: 600;
      letter-spacing: -0.04em;
      color: #ffffff;
    }

    .hero-subtitle {
      margin: 0;
      color: var(--text-soft);
      font-size: 14px;
    }

    .hero-pills,
    .updates-pills,
    .modal-pills,
    .footer-links {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .build-pill,
    .info-pill,
    .status-pill,
    .version-pill,
    .action-button,
    .footer-link,
    .close-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 10px 16px;
      border-radius: var(--radius-pill);
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      font: inherit;
      font-size: 12px;
      font-weight: 500;
      text-decoration: none;
      white-space: nowrap;
      transition: transform 160ms ease, background 160ms ease, border-color 160ms ease;
    }

    .action-button,
    .footer-link,
    .close-button {
      appearance: none;
      cursor: pointer;
    }

    .action-button:hover,
    .footer-link:hover,
    .close-button:hover {
      transform: translateY(-1px);
      background: rgba(255, 255, 255, 0.08);
      border-color: rgba(255, 255, 255, 0.12);
    }

    .action-button.primary {
      background: var(--primary);
      color: #131314;
      border-color: transparent;
      font-weight: 600;
    }

    .action-button.primary:hover {
      background: var(--primary-strong);
    }

    .action-button[disabled] {
      opacity: 0.5;
      cursor: default;
      transform: none;
    }

    .build-pill strong,
    .version-pill {
      font-family: Consolas, "SFMono-Regular", monospace;
    }

    .content-stack {
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .panel,
    .asset-row {
      border: 1px solid var(--line);
      background: var(--surface);
      box-shadow: var(--shadow);
    }

    .panel {
      border-radius: var(--radius-xl);
      padding: 28px;
    }

    .panel-header {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 16px;
    }

    .panel-title {
      margin: 0;
      font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
      font-size: 28px;
      line-height: 1.05;
      letter-spacing: -0.03em;
      color: #ffffff;
    }

    .panel-body {
      margin: 0;
      color: rgba(196, 199, 197, 0.88);
      font-size: 13px;
      line-height: 1.7;
    }

    .banner {
      margin: 0 0 16px;
      padding: 14px 16px;
      border-radius: 20px;
      font-size: 13px;
      line-height: 1.6;
      border: 1px solid transparent;
    }

    .banner.info {
      background: rgba(168, 199, 250, 0.12);
      border-color: rgba(168, 199, 250, 0.18);
      color: var(--primary);
    }

    .banner.error {
      background: rgba(242, 184, 181, 0.12);
      border-color: rgba(242, 184, 181, 0.18);
      color: var(--danger);
    }

    .updates-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }

    .updates-pills {
      justify-content: flex-start;
      margin-top: 14px;
    }

    .section-group {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .asset-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .asset-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      width: 100%;
      padding: 16px 18px;
      border-radius: var(--radius-pill);
      cursor: pointer;
      text-align: left;
      transition: transform 160ms ease, background 160ms ease, border-color 160ms ease;
    }

    .asset-row:hover {
      transform: translateY(-1px);
      background: var(--surface-hover);
      border-color: rgba(255, 255, 255, 0.12);
    }

    .asset-main {
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }

    .asset-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .asset-icon img {
      width: 34px;
      height: 34px;
      object-fit: contain;
      display: block;
    }

    .asset-initials {
      font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
      font-size: 24px;
      font-weight: 700;
      color: var(--primary);
    }

    .asset-copy {
      min-width: 0;
    }

    .asset-name {
      margin: 0;
      font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
      font-size: 17px;
      font-weight: 600;
      color: #ffffff;
    }

    .asset-subtitle {
      margin: 4px 0 0;
      color: rgba(196, 199, 197, 0.76);
      font-size: 12px;
      line-height: 1.55;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 480px;
    }

    .asset-side {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
    }

    .status-pill {
      border-color: transparent;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.04em;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      box-shadow: 0 0 8px currentColor;
    }

    .version-pill {
      color: var(--text-soft);
      background: rgba(19, 19, 20, 0.9);
    }

    .empty-state {
      padding: 10px 0 2px;
      color: rgba(196, 199, 197, 0.72);
      font-size: 13px;
    }

    .footer-links {
      margin-top: 10px;
    }

    .modal-shell {
      position: fixed;
      inset: 0;
      z-index: 20;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 28px;
      background: rgba(10, 10, 10, 0.72);
      backdrop-filter: blur(18px);
    }

    .modal-shell.open {
      display: flex;
    }

    .modal-card {
      width: min(100%, 640px);
      padding: 24px;
      border-radius: 28px;
      background: rgba(30, 31, 32, 0.96);
      border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: 0 22px 52px rgba(0, 0, 0, 0.34);
    }

    .modal-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }

    .modal-title {
      margin: 0;
      font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
      font-size: 30px;
      line-height: 1;
      letter-spacing: -0.04em;
      color: #ffffff;
    }

    .modal-subtitle {
      margin: 8px 0 0;
      color: rgba(196, 199, 197, 0.82);
      font-size: 13px;
    }

    .modal-notes {
      margin: 18px 0 0;
      color: rgba(196, 199, 197, 0.9);
      font-size: 14px;
      line-height: 1.75;
      white-space: pre-wrap;
    }

    .modal-pills {
      justify-content: flex-start;
      margin-top: 16px;
    }

    .modal-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }

    .reveal {
      opacity: 0;
      transform: translateY(18px);
      animation: fadeUp 460ms cubic-bezier(0.25, 1, 0.5, 1) forwards;
    }

    @keyframes fadeUp {
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @media (max-width: 760px) {
      .page-shell { padding: 28px 18px 28px; }
      .panel { padding: 22px; }
      .asset-row {
        align-items: flex-start;
        flex-direction: column;
      }
      .asset-side {
        width: 100%;
        justify-content: space-between;
      }
      .asset-subtitle {
        max-width: none;
        white-space: normal;
      }
      .modal-shell { padding: 18px; }
      .modal-card { padding: 20px; }
      .modal-top {
        flex-direction: column;
        align-items: stretch;
      }
    }
  </style>
</head>
<body>
  <script id="tcollection-state" type="application/json">__TCOLLECTION_STATE__</script>
  <div id="app"></div>
  <div id="asset-modal" class="modal-shell"></div>

  <script>
    const stateNode = document.getElementById("tcollection-state");
    let state = JSON.parse(stateNode.textContent);
    let bridge = null;
    let busyAction = "";
    let activeAssetId = "";

    if (window.qt && window.qt.webChannelTransport && window.QWebChannel) {
      new QWebChannel(window.qt.webChannelTransport, function(channel) {
        bridge = channel.objects.tcollectionBridge || null;
      });
    }

    function escapeHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function getAllAssets() {
      return (state.sections || []).flatMap((section) => section.items || []);
    }

    function findAsset(assetId) {
      return getAllAssets().find((asset) => asset.id === assetId) || null;
    }

    function renderAssetIcon(asset) {
      if (asset.icon_data_url) {
        return `<img src="${asset.icon_data_url}" alt="${escapeHtml(asset.title)} icon">`;
      }
      return `<span class="asset-initials">${escapeHtml(asset.initials || "TC")}</span>`;
    }

    function renderStatusPill(asset) {
      const accent = escapeHtml(asset.status_accent || "#bdc6cf");
      const surface = escapeHtml(asset.status_surface || "#25303c");
      const border = escapeHtml(asset.status_border || "transparent");
      const label = escapeHtml(asset.status_label || asset.status || "Unknown");
      return `
        <span class="status-pill" style="background:${surface};color:${accent};border-color:${border};">
          <span class="status-dot" style="background:${accent};color:${accent};"></span>
          ${label}
        </span>
      `;
    }

    function renderSection(section, sectionIndex) {
      const items = section.items || [];
      const itemsHtml = items.length
        ? items.map((asset, itemIndex) => `
            <button class="asset-row reveal" data-asset-id="${escapeHtml(asset.id)}"
              style="animation-delay:${110 + sectionIndex * 40 + itemIndex * 24}ms;">
              <div class="asset-main">
                <div class="asset-icon">${renderAssetIcon(asset)}</div>
                <div class="asset-copy">
                  <h3 class="asset-name">${escapeHtml(asset.title)}</h3>
                  <p class="asset-subtitle">${escapeHtml(asset.subtitle)}</p>
                </div>
              </div>
              <div class="asset-side">
                <span class="version-pill">${escapeHtml(asset.version)}</span>
                ${renderStatusPill(asset)}
              </div>
            </button>
          `).join("")
        : `<div class="empty-state">Nothing packaged in this section yet.</div>`;

      return `
        <section class="panel section-group reveal" style="animation-delay:${100 + sectionIndex * 35}ms;">
          <div class="panel-header">
            <h2 class="panel-title">${escapeHtml(section.title)}</h2>
            <p class="panel-body">${escapeHtml(section.description)}</p>
          </div>
          <div class="asset-list">${itemsHtml}</div>
        </section>
      `;
    }

    function renderFooterLinks() {
      const links = [];
      if (state.collection && state.collection.repo_url) {
        links.push(`<button class="footer-link" data-action="open-url" data-url="${escapeHtml(state.collection.repo_url)}">Repository</button>`);
      }
      if (state.collection && state.collection.releases_url) {
        links.push(`<button class="footer-link" data-action="open-url" data-url="${escapeHtml(state.collection.releases_url)}">Releases</button>`);
      }
      links.push(`<button class="footer-link" data-action="close-window">Close</button>`);
      return links.join("");
    }

    function renderPage() {
      const updates = state.updates || {};
      const header = state.header || {};
      const banner = state.banner || {};
      const installBusy = busyAction === "install";
      const checkBusy = busyAction === "check";
      const primaryBusy = installBusy || checkBusy;
      const hasInstallAction = !!updates.install_enabled || installBusy;
      const primaryAction = hasInstallAction ? "install-update" : "check-updates";
      let primaryLabel = "Check Updates";
      if (checkBusy) {
        primaryLabel = "Checking...";
      } else if (installBusy) {
        primaryLabel = "Installing...";
      } else if (hasInstallAction) {
        primaryLabel = "Install Update";
      }

      const bannerHtml = banner.message
        ? `<div class="banner ${escapeHtml(banner.tone || "info")}">${escapeHtml(banner.message)}</div>`
        : "";
      const updatesSummary = updates.summary ? `<p class="panel-body">${escapeHtml(updates.summary)}</p>` : "";

      document.getElementById("app").innerHTML = `
        <div class="page-shell">
          <header class="hero reveal" style="animation-delay:50ms;">
            <h1 class="hero-title">${escapeHtml((state.collection && state.collection.display_name) || "TCollection")}</h1>
            <p class="hero-subtitle">${escapeHtml(header.subtitle || "")}</p>
            ${header.description ? `<p class="hero-description">${escapeHtml(header.description)}</p>` : ""}
          </header>

          <main class="content-stack">
            <section class="panel reveal" style="animation-delay:90ms;">
              <div class="panel-header">
                <h2 class="panel-title">Updates</h2>
                ${updatesSummary}
              </div>
              ${bannerHtml}
              <div class="updates-actions">
                <button class="action-button primary" data-action="${primaryAction}" ${primaryBusy ? "disabled" : ""}>
                  ${escapeHtml(primaryLabel)}
                </button>
                <button class="action-button" data-action="open-release-notes" ${updates.notes_url ? "" : "disabled"}>
                  Release Notes
                </button>
              </div>
            </section>

            ${(state.sections || []).map(renderSection).join("")}

            <div class="footer-links reveal" style="animation-delay:160ms;">
              ${renderFooterLinks()}
            </div>
          </main>
        </div>
      `;
    }

    function renderModal() {
      const modal = document.getElementById("asset-modal");
      const asset = findAsset(activeAssetId);
      if (!asset) {
        modal.className = "modal-shell";
        modal.innerHTML = "";
        return;
      }

      const repoButton = asset.repo_url
        ? `<button class="action-button" data-action="open-url" data-url="${escapeHtml(asset.repo_url)}">Repository</button>`
        : "";
      const releasesButton = asset.releases_url
        ? `<button class="action-button" data-action="open-url" data-url="${escapeHtml(asset.releases_url)}">Releases</button>`
        : "";

      modal.className = "modal-shell open";
      modal.innerHTML = `
        <div class="modal-card">
          <div class="modal-top">
            <div>
              <h2 class="modal-title">${escapeHtml(asset.title)}</h2>
              <p class="modal-subtitle">${escapeHtml(asset.subtitle)}</p>
            </div>
            <button class="close-button" data-action="close-modal">Close</button>
          </div>

          <div class="modal-pills">
            <span class="version-pill">${escapeHtml(asset.version)}</span>
            ${renderStatusPill(asset)}
          </div>

          <p class="modal-notes">${escapeHtml(asset.notes)}</p>

          <div class="modal-actions">
            ${repoButton}
            ${releasesButton}
          </div>
        </div>
      `;
    }

    function rerender() {
      renderPage();
      renderModal();
    }

    function callBridge(method, arg) {
      return new Promise((resolve, reject) => {
        if (!bridge || typeof bridge[method] !== "function") {
          reject(new Error("TCollection bridge is not ready."));
          return;
        }

        const callback = function(result) {
          resolve(result);
        };

        if (typeof arg === "undefined") {
          bridge[method](callback);
          return;
        }

        bridge[method](arg, callback);
      });
    }

    async function refreshFromBridge(method, busyKey) {
      busyAction = busyKey;
      rerender();
      try {
        const result = await callBridge(method);
        state = JSON.parse(result);
      } catch (error) {
        console.error(error);
      } finally {
        busyAction = "";
        rerender();
      }
    }

    document.addEventListener("click", async function(event) {
      const assetButton = event.target.closest("[data-asset-id]");
      if (assetButton) {
        activeAssetId = assetButton.getAttribute("data-asset-id") || "";
        renderModal();
        return;
      }

      const actionTarget = event.target.closest("[data-action]");
      if (!actionTarget) {
        if (event.target.id === "asset-modal") {
          activeAssetId = "";
          renderModal();
        }
        return;
      }

      const action = actionTarget.getAttribute("data-action");
      if (action === "close-modal") {
        activeAssetId = "";
        renderModal();
        return;
      }

      if (action === "check-updates") {
        await refreshFromBridge("checkUpdates", "check");
        return;
      }

      if (action === "install-update") {
        if (actionTarget.hasAttribute("disabled")) {
          return;
        }
        await refreshFromBridge("installUpdate", "install");
        return;
      }

      if (action === "open-release-notes") {
        await refreshFromBridge("openReleaseNotes", "notes");
        return;
      }

      if (action === "open-url") {
        const url = actionTarget.getAttribute("data-url") || "";
        if (url && bridge && typeof bridge.openExternalUrl === "function") {
          bridge.openExternalUrl(url, function() {});
        }
        return;
      }

      if (action === "close-window") {
        if (bridge && typeof bridge.closeWindow === "function") {
          bridge.closeWindow();
        }
      }
    });

    document.addEventListener("keydown", function(event) {
      if (event.key === "Escape" && activeAssetId) {
        activeAssetId = "";
        renderModal();
      }
    });

    rerender();
  </script>
</body>
</html>
"""

    def closeEvent(self, event: Any) -> None:  # pragma: no cover - UI lifecycle
        global _SETTINGS_DIALOG
        _SETTINGS_DIALOG = None
        super().closeEvent(event)


def show_settings() -> None:
    """Open the TCollection settings window."""
    global _SETTINGS_DIALOG

    if _SETTINGS_DIALOG is None:
        _SETTINGS_DIALOG = TCollectionSettingsDialog()
    else:
        _SETTINGS_DIALOG.refresh_all()

    _SETTINGS_DIALOG.show()
    _SETTINGS_DIALOG.raise_()
    _SETTINGS_DIALOG.activateWindow()
