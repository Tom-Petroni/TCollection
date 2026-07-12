"""Qt settings dialog for TCollection."""

from __future__ import annotations

from typing import Any

import nuke  # ty: ignore[unresolved-import]

from .loader import get_collection_info, get_nodes, resolve_node_icon_path
from .updater import check_for_updates, get_install_state, prepare_update_for_next_launch

try:  # pragma: no cover - depends on the Nuke runtime
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - fallback for newer runtimes
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]


_SETTINGS_DIALOG: "TCollectionSettingsDialog | None" = None


def _status_style(status: str) -> tuple[str, str]:
    normalized = status.strip().lower()
    if normalized == "stable":
        return "#1f3a27", "#99e0ad"
    if normalized == "test":
        return "#463519", "#f0cd88"
    if normalized == "hold":
        return "#3f2c42", "#ddb6e5"
    return "#25303c", "#b6c1cb"


class NodeCardWidget(QtWidgets.QFrame):
    """Card row used in the Nodes tab."""

    def __init__(self, entry: dict[str, Any]) -> None:
        super().__init__()
        self.setObjectName("NodeCard")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        icon_holder = QtWidgets.QLabel()
        icon_holder.setFixedSize(42, 42)
        icon_holder.setAlignment(QtCore.Qt.AlignCenter)
        icon_holder.setObjectName("NodeIcon")
        icon_path = resolve_node_icon_path(str(entry.get("key", "")).strip())
        if icon_path:
            pixmap = QtGui.QPixmap(icon_path)
            if not pixmap.isNull():
                icon_holder.setPixmap(
                    pixmap.scaled(
                        22,
                        22,
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation,
                    )
                )
        else:
            icon_holder.setText(str(entry.get("label", "?"))[:1].upper())
        layout.addWidget(icon_holder, 0, QtCore.Qt.AlignTop)

        copy = QtWidgets.QVBoxLayout()
        copy.setSpacing(4)

        header_row = QtWidgets.QHBoxLayout()
        header_row.setSpacing(8)

        title = QtWidgets.QLabel(str(entry.get("label", entry.get("key", ""))).strip())
        title.setObjectName("NodeTitle")
        header_row.addWidget(title)

        version = QtWidgets.QLabel(str(entry.get("version", "")).strip())
        version.setObjectName("NodeVersionPill")
        header_row.addWidget(version, 0, QtCore.Qt.AlignVCenter)
        header_row.addStretch(1)

        status_text = str(entry.get("status", "")).strip() or "unknown"
        status_bg, status_fg = _status_style(status_text)
        status = QtWidgets.QLabel(status_text.upper())
        status.setObjectName("NodeStatusPill")
        status.setStyleSheet(
            f"background: {status_bg}; color: {status_fg}; border: 1px solid transparent;"
        )
        header_row.addWidget(status, 0, QtCore.Qt.AlignVCenter)
        copy.addLayout(header_row)

        subtitle = QtWidgets.QLabel(str(entry.get("class_name", "")).strip() or "Node runtime")
        subtitle.setObjectName("NodeSubtitle")
        copy.addWidget(subtitle)

        notes = str(entry.get("notes", "")).strip()
        if notes:
            notes_label = QtWidgets.QLabel(notes)
            notes_label.setObjectName("NodeNotes")
            notes_label.setWordWrap(True)
            copy.addWidget(notes_label)

        layout.addLayout(copy, 1)


class TCollectionSettingsDialog(QtWidgets.QDialog):
    """Central settings window for collection status and updates."""

    def __init__(self) -> None:
        super().__init__()
        self._update_result: dict[str, Any] | None = None
        self.setWindowTitle("TCollection Settings")
        self.setObjectName("TCollectionSettingsDialog")
        self.setMinimumSize(1040, 760)
        self.setModal(False)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog#TCollectionSettingsDialog {
                background: #0a0a0a;
                color: #f5f5f5;
                font-family: "DM Sans", "Manrope", "Segoe UI", sans-serif;
            }
            QFrame#TopBar {
                background: rgba(18, 18, 18, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 26px;
            }
            QFrame#HeroCard, QFrame#PanelCard, QFrame#NodeCard {
                background: rgba(18, 18, 18, 0.82);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 28px;
            }
            QFrame#StatCard {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 22px;
            }
            QLabel#BrandTitle {
                font-size: 14px;
                font-weight: 500;
                letter-spacing: 0.04em;
                color: #f5f5f5;
            }
            QLabel#VersionPill {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 13px;
                color: #b8b8b8;
                font-size: 11px;
                font-family: Consolas, "SFMono-Regular", monospace;
                padding: 5px 9px;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
                top: -1px;
            }
            QTabBar::tab {
                background: transparent;
                color: #8f8f8f;
                border: none;
                padding: 10px 18px;
                margin: 0 2px;
                border-radius: 18px;
                font-size: 12px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: rgba(255, 255, 255, 0.04);
                color: #d4d4d4;
            }
            QLabel#HeroEyebrow {
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 0.22em;
                text-transform: uppercase;
                color: #7d7d7d;
            }
            QLabel#HeroTitle {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 34px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#HeroBody {
                font-size: 14px;
                line-height: 1.6;
                color: #b9b9b9;
            }
            QLabel#StatusPill {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                color: #ededed;
                font-size: 11px;
                font-weight: 600;
                padding: 5px 10px;
            }
            QLabel#StatKicker {
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.18em;
                text-transform: uppercase;
                color: #6f6f6f;
            }
            QLabel#StatValue {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 20px;
                font-weight: 600;
                color: #f7f7f7;
            }
            QLabel#StatNote {
                font-size: 12px;
                color: #9a9a9a;
            }
            QLabel#SectionTitle {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 24px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#SectionBody {
                font-size: 13px;
                line-height: 1.6;
                color: #afafaf;
            }
            QLabel#InfoLabel {
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.15em;
                text-transform: uppercase;
                color: #6f6f6f;
            }
            QLabel#InfoValue {
                font-size: 13px;
                color: #ececec;
            }
            QLabel#NodeTitle {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 19px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#NodeSubtitle {
                font-size: 12px;
                color: #9e9e9e;
            }
            QLabel#NodeNotes {
                font-size: 12px;
                line-height: 1.5;
                color: #7e7e7e;
            }
            QLabel#NodeVersionPill {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 11px;
                color: #bdbdbd;
                font-size: 10px;
                font-family: Consolas, "SFMono-Regular", monospace;
                padding: 4px 8px;
            }
            QLabel#NodeStatusPill {
                border-radius: 11px;
                font-size: 10px;
                font-weight: 700;
                padding: 4px 8px;
            }
            QLabel#NodeIcon {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 21px;
                color: #d9d9d9;
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 13px;
                font-weight: 700;
            }
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border: none;
                margin: 0 0 10px 0;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 8px 0 8px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.14);
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #f2f2f2;
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 18px;
                padding: 11px 18px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.09);
            }
            QPushButton:disabled {
                color: #6f6f6f;
                border-color: rgba(255, 255, 255, 0.05);
                background: rgba(255, 255, 255, 0.02);
            }
            QPushButton#PrimaryButton {
                background: rgba(255, 255, 255, 0.9);
                color: #0a0a0a;
                border: 1px solid rgba(255, 255, 255, 0.9);
            }
            QPushButton#PrimaryButton:hover {
                background: #ffffff;
            }
            QFrame#UpdateStateCard {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 22px;
            }
            QLabel#UpdateStateTitle {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 20px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#UpdateStateText, QLabel#AboutText {
                font-size: 13px;
                line-height: 1.7;
                color: #b6b6b6;
            }
            QLabel#ReleaseLink {
                color: #d0d0d0;
                font-size: 12px;
            }
            """
        )

        self.resize(1120, 820)
        self.setFont(QtGui.QFont("DM Sans", 10))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)

        top_bar = QtWidgets.QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(18, 12, 18, 12)
        top_layout.setSpacing(14)

        brand = QtWidgets.QLabel("Thomas Petroni / TCollection")
        brand.setObjectName("BrandTitle")
        top_layout.addWidget(brand)

        self._version_pill = QtWidgets.QLabel("v0.0.0")
        self._version_pill.setObjectName("VersionPill")
        top_layout.addWidget(self._version_pill, 0, QtCore.Qt.AlignLeft)
        top_layout.addStretch(1)

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.close)
        top_layout.addWidget(close_button)
        layout.addWidget(top_bar)

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QtWidgets.QTabWidget.North)
        self._tabs.setMovable(False)
        layout.addWidget(self._tabs, 1)

        self._overview_page = self._build_overview_page()
        self._nodes_page = self._build_nodes_page()
        self._updates_page = self._build_updates_page()
        self._about_page = self._build_about_page()

        self._tabs.addTab(self._overview_page, "Overview")
        self._tabs.addTab(self._nodes_page, "Nodes")
        self._tabs.addTab(self._updates_page, "Updates")
        self._tabs.addTab(self._about_page, "About")

    def _build_overview_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(18)

        hero = QtWidgets.QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QtWidgets.QVBoxLayout(hero)
        hero_layout.setContentsMargins(26, 26, 26, 26)
        hero_layout.setSpacing(10)

        eyebrow = QtWidgets.QLabel("Collection manager")
        eyebrow.setObjectName("HeroEyebrow")
        hero_layout.addWidget(eyebrow)

        self._hero_title = QtWidgets.QLabel("TCollection")
        self._hero_title.setObjectName("HeroTitle")
        hero_layout.addWidget(self._hero_title)

        self._hero_body = QtWidgets.QLabel("")
        self._hero_body.setObjectName("HeroBody")
        self._hero_body.setWordWrap(True)
        hero_layout.addWidget(self._hero_body)

        self._hero_status = QtWidgets.QLabel("")
        self._hero_status.setObjectName("StatusPill")
        hero_layout.addWidget(self._hero_status, 0, QtCore.Qt.AlignLeft)
        layout.addWidget(hero)

        stats_row = QtWidgets.QHBoxLayout()
        stats_row.setSpacing(14)
        layout.addLayout(stats_row)

        self._collection_version = self._build_stat_card("Collection Version", "Installed release package.")
        self._managed_version = self._build_stat_card("Managed Version", "Currently active managed version.")
        self._pending_version = self._build_stat_card("Pending Version", "Will activate on next Nuke launch.")
        self._node_count = self._build_stat_card("Visible Nodes", "Stable and test nodes registered in the menu.")

        stats_row.addWidget(self._collection_version["card"], 1)
        stats_row.addWidget(self._managed_version["card"], 1)
        stats_row.addWidget(self._pending_version["card"], 1)
        stats_row.addWidget(self._node_count["card"], 1)

        info_card = QtWidgets.QFrame()
        info_card.setObjectName("PanelCard")
        info_layout = QtWidgets.QVBoxLayout(info_card)
        info_layout.setContentsMargins(24, 24, 24, 24)
        info_layout.setSpacing(14)

        title = QtWidgets.QLabel("Install Paths")
        title.setObjectName("SectionTitle")
        info_layout.addWidget(title)

        body = QtWidgets.QLabel(
            "This section tracks where the runtime is currently loaded from and where managed updates are staged."
        )
        body.setObjectName("SectionBody")
        body.setWordWrap(True)
        info_layout.addWidget(body)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 10, 0, 0)
        form.setSpacing(12)
        self._runtime_root = self._build_info_value(word_wrap=True)
        self._managed_root = self._build_info_value(word_wrap=True)
        self._versions_root = self._build_info_value(word_wrap=True)
        form.addRow(self._build_info_label("Runtime Root"), self._runtime_root)
        form.addRow(self._build_info_label("Managed Root"), self._managed_root)
        form.addRow(self._build_info_label("Versions Root"), self._versions_root)
        info_layout.addLayout(form)
        layout.addWidget(info_card)

        layout.addStretch(1)
        return page

    def _build_nodes_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(18)

        intro = QtWidgets.QFrame()
        intro.setObjectName("PanelCard")
        intro_layout = QtWidgets.QVBoxLayout(intro)
        intro_layout.setContentsMargins(24, 24, 24, 24)
        intro_layout.setSpacing(8)

        title = QtWidgets.QLabel("Nodes")
        title.setObjectName("SectionTitle")
        intro_layout.addWidget(title)

        self._nodes_intro = QtWidgets.QLabel("")
        self._nodes_intro.setObjectName("SectionBody")
        self._nodes_intro.setWordWrap(True)
        intro_layout.addWidget(self._nodes_intro)
        layout.addWidget(intro)

        self._nodes_list = QtWidgets.QListWidget()
        self._nodes_list.setSpacing(0)
        layout.addWidget(self._nodes_list, 1)
        return page

    def _build_updates_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(18)

        state_card = QtWidgets.QFrame()
        state_card.setObjectName("HeroCard")
        state_layout = QtWidgets.QVBoxLayout(state_card)
        state_layout.setContentsMargins(26, 24, 26, 24)
        state_layout.setSpacing(10)

        kicker = QtWidgets.QLabel("Managed updates")
        kicker.setObjectName("HeroEyebrow")
        state_layout.addWidget(kicker)

        self._update_state_title = QtWidgets.QLabel("Updates")
        self._update_state_title.setObjectName("UpdateStateTitle")
        state_layout.addWidget(self._update_state_title)

        self._update_summary = QtWidgets.QLabel("")
        self._update_summary.setObjectName("UpdateStateText")
        self._update_summary.setWordWrap(True)
        state_layout.addWidget(self._update_summary)
        layout.addWidget(state_card)

        split = QtWidgets.QHBoxLayout()
        split.setSpacing(14)
        layout.addLayout(split)

        versions_card = QtWidgets.QFrame()
        versions_card.setObjectName("UpdateStateCard")
        versions_layout = QtWidgets.QVBoxLayout(versions_card)
        versions_layout.setContentsMargins(24, 24, 24, 24)
        versions_layout.setSpacing(12)
        versions_title = QtWidgets.QLabel("Release State")
        versions_title.setObjectName("SectionTitle")
        versions_layout.addWidget(versions_title)

        versions_form = QtWidgets.QFormLayout()
        versions_form.setContentsMargins(0, 4, 0, 0)
        versions_form.setSpacing(12)
        self._update_current = self._build_info_value()
        self._update_latest = self._build_info_value()
        self._update_channel = self._build_info_value()
        self._release_link = self._build_info_value(word_wrap=True)
        versions_form.addRow(self._build_info_label("Current"), self._update_current)
        versions_form.addRow(self._build_info_label("Latest"), self._update_latest)
        versions_form.addRow(self._build_info_label("Channel"), self._update_channel)
        versions_form.addRow(self._build_info_label("Release Notes"), self._release_link)
        versions_layout.addLayout(versions_form)
        split.addWidget(versions_card, 1)

        actions_card = QtWidgets.QFrame()
        actions_card.setObjectName("UpdateStateCard")
        actions_layout = QtWidgets.QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(24, 24, 24, 24)
        actions_layout.setSpacing(14)
        actions_title = QtWidgets.QLabel("Actions")
        actions_title.setObjectName("SectionTitle")
        actions_layout.addWidget(actions_title)

        actions_body = QtWidgets.QLabel(
            "Check the latest GitHub release, download the package into the managed versions folder, then relaunch Nuke."
        )
        actions_body.setObjectName("SectionBody")
        actions_body.setWordWrap(True)
        actions_layout.addWidget(actions_body)

        self._check_button = QtWidgets.QPushButton("Check for Updates")
        self._check_button.setObjectName("PrimaryButton")
        self._check_button.clicked.connect(self._check_for_updates)
        actions_layout.addWidget(self._check_button)

        self._prepare_button = QtWidgets.QPushButton("Download for Next Launch")
        self._prepare_button.setEnabled(False)
        self._prepare_button.clicked.connect(self._prepare_update)
        actions_layout.addWidget(self._prepare_button)

        self._notes_button = QtWidgets.QPushButton("Open Release Notes")
        self._notes_button.setEnabled(False)
        self._notes_button.clicked.connect(self._open_release_notes)
        actions_layout.addWidget(self._notes_button)
        actions_layout.addStretch(1)
        split.addWidget(actions_card, 1)

        layout.addStretch(1)
        return page

    def _build_about_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(18)

        about_card = QtWidgets.QFrame()
        about_card.setObjectName("PanelCard")
        about_layout = QtWidgets.QVBoxLayout(about_card)
        about_layout.setContentsMargins(28, 28, 28, 28)
        about_layout.setSpacing(12)

        title = QtWidgets.QLabel("About TCollection")
        title.setObjectName("SectionTitle")
        about_layout.addWidget(title)

        text = QtWidgets.QLabel(
            "TCollection is the curated runtime layer for your Nuke tools. "
            "It keeps node installation simple for artists, tracks versions cleanly, "
            "and prepares updates so a restart is enough to switch to the next package.\n\n"
            "The UI direction here follows the same language as your portfolio: "
            "deep neutral backgrounds, floating pill navigation, soft borders, and a more cinematic presentation."
        )
        text.setObjectName("AboutText")
        text.setWordWrap(True)
        about_layout.addWidget(text)

        self._about_version = self._build_info_value()
        self._about_repo = self._build_info_value(word_wrap=True)
        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 8, 0, 0)
        form.setSpacing(12)
        form.addRow(self._build_info_label("Collection Version"), self._about_version)
        form.addRow(self._build_info_label("Repository"), self._about_repo)
        about_layout.addLayout(form)
        layout.addWidget(about_card)
        layout.addStretch(1)
        return page

    def _build_stat_card(self, kicker: str, note: str) -> dict[str, Any]:
        card = QtWidgets.QFrame()
        card.setObjectName("StatCard")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        kicker_label = QtWidgets.QLabel(kicker)
        kicker_label.setObjectName("StatKicker")
        value_label = QtWidgets.QLabel("")
        value_label.setObjectName("StatValue")
        note_label = QtWidgets.QLabel(note)
        note_label.setObjectName("StatNote")
        note_label.setWordWrap(True)

        layout.addWidget(kicker_label)
        layout.addWidget(value_label)
        layout.addWidget(note_label)
        layout.addStretch(1)

        return {"card": card, "value": value_label}

    def _build_info_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("InfoLabel")
        return label

    def _build_info_value(self, word_wrap: bool = False) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel("")
        label.setObjectName("InfoValue")
        label.setWordWrap(word_wrap)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        return label

    def refresh_all(self) -> None:
        self._refresh_collection_state()
        self._refresh_nodes_list()
        self._refresh_update_summary()

    def _refresh_collection_state(self) -> None:
        info = get_collection_info()
        state = get_install_state()
        version = str(info.get("version", "unknown"))
        nodes = get_nodes()
        visible_nodes = [entry for entry in nodes if str(entry.get("class_name", "")).strip()]

        self._version_pill.setText(f"v{version}")
        self._hero_title.setText(str(info.get("display_name", "TCollection")))
        self._hero_body.setText(
            "A clean, artist-friendly collection runtime for your Nuke nodes. "
            "Versions stay centralized, updates stay simple, and the menu remains focused."
        )
        self._hero_status.setText("Menu-ready collection with managed GitHub release updates")

        self._collection_version["value"].setText(version)
        self._managed_version["value"].setText(state.get("current_version", "") or "Not installed")
        self._pending_version["value"].setText(state.get("pending_version", "") or "None")
        self._node_count["value"].setText(str(len(visible_nodes)))

        self._runtime_root.setText(state.get("runtime_root", ""))
        self._managed_root.setText(state.get("managed_root", ""))
        self._versions_root.setText(state.get("versions_root", ""))

        self._nodes_intro.setText(
            f"{len(visible_nodes)} visible node entries are currently registered in the collection manifest."
        )

        self._about_version.setText(version)
        repo_url = str(info.get("links", {}).get("repo_url", "")).strip()
        self._about_repo.setText(repo_url or "No repository URL configured.")

    def _refresh_nodes_list(self) -> None:
        nodes = sorted(
            get_nodes(),
            key=lambda entry: str(entry.get("label", entry.get("key", ""))).lower(),
        )

        self._nodes_list.clear()
        for entry in nodes:
            if not str(entry.get("class_name", "")).strip():
                continue

            item = QtWidgets.QListWidgetItem()
            card = NodeCardWidget(entry)
            item.setSizeHint(card.sizeHint())
            self._nodes_list.addItem(item)
            self._nodes_list.setItemWidget(item, card)

    def _refresh_update_summary(self) -> None:
        info = get_collection_info()
        current_collection_version = str(info.get("version", "unknown")).strip()

        if self._update_result is None:
            self._update_state_title.setText("Updates")
            self._update_summary.setText(
                "No remote release has been checked yet. Query GitHub to compare the installed package with the latest published collection."
            )
            self._update_current.setText(current_collection_version)
            self._update_latest.setText("Not checked")
            self._update_channel.setText("stable")
            self._release_link.setText("No release notes loaded.")
            self._prepare_button.setEnabled(False)
            self._notes_button.setEnabled(False)
            return

        available = bool(self._update_result.get("available", False))
        latest_version = str(self._update_result.get("latest_version", "")).strip() or current_collection_version
        current_version = str(self._update_result.get("current_version", "")).strip() or current_collection_version
        reason = str(self._update_result.get("reason", "")).strip()
        channel = str(self._update_result.get("channel", "")).strip() or "stable"
        notes_url = str(self._update_result.get("notes_url", "")).strip()

        if available:
            self._update_state_title.setText("A new release is available")
            self._update_summary.setText(
                f"TCollection {latest_version} is ready to download. "
                f"You are currently on {current_version}. {reason}"
            )
        else:
            self._update_state_title.setText("You are up to date")
            self._update_summary.setText(
                f"TCollection {current_version} already matches the latest published release. {reason}"
            )

        self._update_current.setText(current_version)
        self._update_latest.setText(latest_version)
        self._update_channel.setText(channel)
        self._release_link.setText(notes_url or "No release notes URL available.")
        self._prepare_button.setEnabled(available)
        self._notes_button.setEnabled(bool(notes_url))

    def _check_for_updates(self) -> None:
        self._check_button.setEnabled(False)
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self._update_result = check_for_updates()
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
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self._check_button.setEnabled(True)

        self._refresh_update_summary()

    def _prepare_update(self) -> None:
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            result = prepare_update_for_next_launch(self._update_result)
        except Exception as exc:
            nuke.message(f"TCollection: failed to prepare the update.\n\n{exc}")  # ty: ignore[unresolved-attribute]
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self._refresh_collection_state()
        self._update_summary.setText(
            f"TCollection {result['version']} has been downloaded into the managed versions folder. Restart Nuke to activate it."
        )
        self._prepare_button.setEnabled(False)
        nuke.message(  # ty: ignore[unresolved-attribute]
            "TCollection update prepared.\n\n"
            f"Version: {result['version']}\n"
            "Restart Nuke to activate it."
        )

    def _open_release_notes(self) -> None:
        if self._update_result is None:
            return

        notes_url = str(self._update_result.get("notes_url", "")).strip()
        if not notes_url:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(notes_url))

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
