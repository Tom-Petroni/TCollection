"""Single-page Qt settings dialog for TCollection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import nuke  # ty: ignore[unresolved-import]

from .loader import get_collection_info, get_nodes, resolve_node_icon_path
from .updater import check_for_updates, get_install_state, prepare_update_for_next_launch

try:  # pragma: no cover - depends on the Nuke runtime
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - fallback for newer runtimes
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]


ROOT_DIR = Path(__file__).resolve().parents[1]
_SETTINGS_DIALOG: "TCollectionSettingsDialog | None" = None


def _status_style(status: str) -> tuple[str, str]:
    normalized = status.strip().lower()
    if normalized == "stable":
        return "#1f3a27", "#9ce2b0"
    if normalized == "test":
        return "#47371d", "#f4d18f"
    if normalized == "hold":
        return "#3b2d42", "#dfbbe6"
    return "#25303c", "#bdc6cf"


def _clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


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


class AssetCardWidget(QtWidgets.QFrame):
    """Card used for nodes, gizmos, and scripts."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        badge_text: str,
        notes: str = "",
        icon_path: str = "",
        badge_status: str = "",
    ) -> None:
        super().__init__()
        self.setObjectName("AssetCard")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        icon_holder = QtWidgets.QLabel()
        icon_holder.setFixedSize(44, 44)
        icon_holder.setAlignment(QtCore.Qt.AlignCenter)
        icon_holder.setObjectName("AssetIcon")

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
            icon_holder.setText((title or "?")[:1].upper())

        layout.addWidget(icon_holder, 0, QtCore.Qt.AlignTop)

        content = QtWidgets.QVBoxLayout()
        content.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("AssetTitle")
        header.addWidget(title_label)

        badge = QtWidgets.QLabel(badge_text)
        badge.setObjectName("AssetBadge")
        if badge_status:
            badge_bg, badge_fg = _status_style(badge_status)
            badge.setStyleSheet(
                f"background: {badge_bg}; color: {badge_fg}; border: 1px solid transparent;"
            )
        header.addWidget(badge, 0, QtCore.Qt.AlignVCenter)
        header.addStretch(1)
        content.addLayout(header)

        subtitle_label = QtWidgets.QLabel(subtitle)
        subtitle_label.setObjectName("AssetSubtitle")
        content.addWidget(subtitle_label)

        if notes:
            notes_label = QtWidgets.QLabel(notes)
            notes_label.setObjectName("AssetNotes")
            notes_label.setWordWrap(True)
            content.addWidget(notes_label)

        layout.addLayout(content, 1)


class TCollectionSettingsDialog(QtWidgets.QDialog):
    """Single scrollable settings page inspired by the portfolio layout."""

    def __init__(self) -> None:
        super().__init__()
        self._update_result: dict[str, Any] | None = None
        self._fade_animation: QtCore.QPropertyAnimation | None = None
        self.setWindowTitle("TCollection Settings")
        self.setObjectName("TCollectionSettingsDialog")
        self.setMinimumSize(1040, 820)
        self.setModal(False)
        self._build_ui()
        self.refresh_all()
        self._animate_in()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog#TCollectionSettingsDialog {
                background: #0a0a0a;
                color: #f5f5f5;
                font-family: "DM Sans", "Manrope", "Segoe UI", sans-serif;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QWidget#ScrollContent {
                background: transparent;
            }
            QFrame#FloatingBar {
                background: rgba(18, 18, 18, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 26px;
            }
            QFrame#HeroCard, QFrame#PanelCard, QFrame#AssetCard, QFrame#StatCard {
                background: rgba(18, 18, 18, 0.82);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            QFrame#HeroCard, QFrame#PanelCard {
                border-radius: 30px;
            }
            QFrame#AssetCard {
                border-radius: 22px;
            }
            QFrame#StatCard {
                border-radius: 22px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.07);
            }
            QLabel#FloatingText {
                font-size: 12px;
                font-weight: 500;
                color: #e6e6e6;
                letter-spacing: 0.04em;
            }
            QLabel#VersionPill {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 13px;
                color: #bbbbbb;
                font-size: 11px;
                font-family: Consolas, "SFMono-Regular", monospace;
                padding: 5px 9px;
            }
            QLabel#HeroKicker {
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 0.22em;
                text-transform: uppercase;
                color: #7d7d7d;
            }
            QLabel#HeroTitle {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 42px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#HeroBody {
                font-size: 14px;
                line-height: 1.7;
                color: #b6b6b6;
            }
            QLabel#HeroPill {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                color: #ededed;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 12px;
            }
            QLabel#SectionTitle {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 28px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#SectionBody {
                font-size: 13px;
                line-height: 1.7;
                color: #afafaf;
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
                font-size: 22px;
                font-weight: 600;
                color: #f7f7f7;
            }
            QLabel#StatNote {
                font-size: 12px;
                color: #9a9a9a;
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
            QLabel#AssetTitle {
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 18px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#AssetSubtitle {
                font-size: 12px;
                color: #a0a0a0;
            }
            QLabel#AssetNotes {
                font-size: 12px;
                line-height: 1.6;
                color: #7f7f7f;
            }
            QLabel#AssetBadge {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 11px;
                color: #bdbdbd;
                font-size: 10px;
                font-family: Consolas, "SFMono-Regular", monospace;
                padding: 4px 8px;
            }
            QLabel#AssetIcon {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 22px;
                color: #d9d9d9;
                font-family: "Manrope", "DM Sans", "Segoe UI", sans-serif;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#EmptyState {
                font-size: 13px;
                color: #8c8c8c;
                padding: 4px 0;
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
            """
        )

        self.resize(1140, 860)
        self.setFont(QtGui.QFont("DM Sans", 10))

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(18)

        floating_bar = QtWidgets.QFrame()
        floating_bar.setObjectName("FloatingBar")
        floating_layout = QtWidgets.QHBoxLayout(floating_bar)
        floating_layout.setContentsMargins(18, 12, 18, 12)
        floating_layout.setSpacing(12)

        self._floating_label = QtWidgets.QLabel("Thomas Petroni / TCollection")
        self._floating_label.setObjectName("FloatingText")
        floating_layout.addWidget(self._floating_label)

        self._version_pill = QtWidgets.QLabel("v0.0.0")
        self._version_pill.setObjectName("VersionPill")
        floating_layout.addWidget(self._version_pill, 0, QtCore.Qt.AlignLeft)
        floating_layout.addStretch(1)

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.close)
        floating_layout.addWidget(close_button)
        outer.addWidget(floating_bar)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        outer.addWidget(self._scroll, 1)

        scroll_content = QtWidgets.QWidget()
        scroll_content.setObjectName("ScrollContent")
        self._scroll.setWidget(scroll_content)

        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 10)
        scroll_layout.setSpacing(0)

        center_wrapper = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center_wrapper)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(18)
        scroll_layout.addWidget(center_wrapper, 0, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)

        self._content_frame = QtWidgets.QFrame()
        self._content_frame.setObjectName("ContentFrame")
        self._content_frame.setMaximumWidth(980)
        content_layout = QtWidgets.QVBoxLayout(self._content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)
        center_layout.addWidget(self._content_frame)

        self._hero_card = self._build_hero_card()
        self._updates_card = self._build_updates_card()
        self._assets_intro_card = self._build_assets_intro_card()
        self._nodes_card, self._nodes_items_layout = self._build_asset_section_card(
            "Nodes",
            "Native nodes currently tracked by the collection package.",
        )
        self._gizmos_card, self._gizmos_items_layout = self._build_asset_section_card(
            "Gizmos",
            "Reusable gizmos shipped in the collection package.",
        )
        self._scripts_card, self._scripts_items_layout = self._build_asset_section_card(
            "Scripts",
            "Utility scripts available alongside the collection runtime.",
        )

        content_layout.addWidget(self._hero_card)
        content_layout.addWidget(self._updates_card)
        content_layout.addWidget(self._assets_intro_card)
        content_layout.addWidget(self._nodes_card)
        content_layout.addWidget(self._gizmos_card)
        content_layout.addWidget(self._scripts_card)
        content_layout.addStretch(1)

    def _build_hero_card(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("HeroCard")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(30, 34, 30, 34)
        layout.setSpacing(12)

        self._hero_kicker = QtWidgets.QLabel("Collection manager")
        self._hero_kicker.setObjectName("HeroKicker")
        self._hero_kicker.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._hero_kicker)

        self._hero_title = QtWidgets.QLabel("TCollection")
        self._hero_title.setObjectName("HeroTitle")
        self._hero_title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._hero_title)

        self._hero_body = QtWidgets.QLabel("")
        self._hero_body.setObjectName("HeroBody")
        self._hero_body.setAlignment(QtCore.Qt.AlignCenter)
        self._hero_body.setWordWrap(True)
        layout.addWidget(self._hero_body)

        self._hero_pill = QtWidgets.QLabel("")
        self._hero_pill.setObjectName("HeroPill")
        self._hero_pill.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._hero_pill, 0, QtCore.Qt.AlignHCenter)
        return card

    def _build_updates_card(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("PanelCard")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("Updates & Versions")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        body = QtWidgets.QLabel(
            "Check the latest GitHub release, prepare the next install for the following Nuke launch, and keep an eye on the managed package state."
        )
        body.setObjectName("SectionBody")
        body.setWordWrap(True)
        layout.addWidget(body)

        stats_row = QtWidgets.QHBoxLayout()
        stats_row.setSpacing(14)
        layout.addLayout(stats_row)

        self._collection_version = self._build_stat_card("Collection Version", "Installed collection package.")
        self._managed_version = self._build_stat_card("Managed Version", "Currently active managed version.")
        self._pending_version = self._build_stat_card("Pending Version", "Will activate on next launch.")
        self._latest_version = self._build_stat_card("Latest Release", "Last published GitHub release.")

        stats_row.addWidget(self._collection_version["card"], 1)
        stats_row.addWidget(self._managed_version["card"], 1)
        stats_row.addWidget(self._pending_version["card"], 1)
        stats_row.addWidget(self._latest_version["card"], 1)

        info_form = QtWidgets.QFormLayout()
        info_form.setContentsMargins(0, 6, 0, 0)
        info_form.setSpacing(12)
        self._update_summary = self._build_info_value(word_wrap=True)
        self._update_channel = self._build_info_value()
        self._release_link = self._build_info_value(word_wrap=True)
        self._runtime_root = self._build_info_value(word_wrap=True)
        info_form.addRow(self._build_info_label("Update State"), self._update_summary)
        info_form.addRow(self._build_info_label("Channel"), self._update_channel)
        info_form.addRow(self._build_info_label("Release Notes"), self._release_link)
        info_form.addRow(self._build_info_label("Runtime Root"), self._runtime_root)
        layout.addLayout(info_form)

        buttons_row = QtWidgets.QHBoxLayout()
        buttons_row.setSpacing(12)

        self._check_button = QtWidgets.QPushButton("Check for Updates")
        self._check_button.setObjectName("PrimaryButton")
        self._check_button.clicked.connect(self._check_for_updates)
        buttons_row.addWidget(self._check_button)

        self._prepare_button = QtWidgets.QPushButton("Download for Next Launch")
        self._prepare_button.setEnabled(False)
        self._prepare_button.clicked.connect(self._prepare_update)
        buttons_row.addWidget(self._prepare_button)

        self._notes_button = QtWidgets.QPushButton("Open Release Notes")
        self._notes_button.setEnabled(False)
        self._notes_button.clicked.connect(self._open_release_notes)
        buttons_row.addWidget(self._notes_button)

        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)
        return card

    def _build_assets_intro_card(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("PanelCard")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Collection Contents")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self._assets_intro = QtWidgets.QLabel("")
        self._assets_intro.setObjectName("SectionBody")
        self._assets_intro.setWordWrap(True)
        layout.addWidget(self._assets_intro)
        return card

    def _build_asset_section_card(
        self,
        title_text: str,
        body_text: str,
    ) -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
        card = QtWidgets.QFrame()
        card.setObjectName("PanelCard")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)

        title = QtWidgets.QLabel(title_text)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        body = QtWidgets.QLabel(body_text)
        body.setObjectName("SectionBody")
        body.setWordWrap(True)
        layout.addWidget(body)

        items_widget = QtWidgets.QWidget()
        items_layout = QtWidgets.QVBoxLayout(items_widget)
        items_layout.setContentsMargins(0, 8, 0, 0)
        items_layout.setSpacing(10)
        layout.addWidget(items_widget)
        return card, items_layout

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

    def _animate_in(self) -> None:
        effect = QtWidgets.QGraphicsOpacityEffect(self._content_frame)
        self._content_frame.setGraphicsEffect(effect)
        self._fade_animation = QtCore.QPropertyAnimation(effect, b"opacity", self)
        self._fade_animation.setDuration(260)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._fade_animation.start()

    def refresh_all(self) -> None:
        self._refresh_collection_state()
        self._refresh_asset_lists()
        self._refresh_update_summary()

    def _refresh_collection_state(self) -> None:
        info = get_collection_info()
        state = get_install_state()
        version = str(info.get("version", "unknown"))
        nodes = [entry for entry in get_nodes() if str(entry.get("class_name", "")).strip()]
        gizmo_files = _iter_runtime_files("gizmos")
        script_files = _iter_runtime_files("scripts")

        self._version_pill.setText(f"v{version}")
        self._hero_title.setText(str(info.get("display_name", "TCollection")))
        self._hero_body.setText(
            "A single place inside Nuke to track the collection version, prepare updates, and browse the current package contents."
        )
        self._hero_pill.setText("Single-page collection settings inspired by your portfolio layout")

        self._collection_version["value"].setText(version)
        self._managed_version["value"].setText(state.get("current_version", "") or "Not installed")
        self._pending_version["value"].setText(state.get("pending_version", "") or "None")
        self._runtime_root.setText(state.get("runtime_root", ""))

        self._assets_intro.setText(
            f"The current package exposes {len(nodes)} nodes, {len(gizmo_files)} gizmo files, and {len(script_files)} script files."
        )

    def _refresh_asset_lists(self) -> None:
        self._populate_nodes()
        self._populate_gizmos()
        self._populate_scripts()

    def _populate_nodes(self) -> None:
        _clear_layout(self._nodes_items_layout)
        nodes = sorted(
            [entry for entry in get_nodes() if str(entry.get("class_name", "")).strip()],
            key=lambda entry: str(entry.get("label", entry.get("key", ""))).lower(),
        )

        if not nodes:
            empty = QtWidgets.QLabel("No node entries are currently available in the collection.")
            empty.setObjectName("EmptyState")
            self._nodes_items_layout.addWidget(empty)
            return

        for entry in nodes:
            node_key = str(entry.get("key", "")).strip()
            label = str(entry.get("label", node_key)).strip() or node_key
            version = str(entry.get("version", "")).strip()
            status = str(entry.get("status", "")).strip() or "unknown"
            subtitle = str(entry.get("class_name", "")).strip() or "Node runtime"
            notes = str(entry.get("notes", "")).strip()
            icon_path = resolve_node_icon_path(node_key)
            card = AssetCardWidget(
                title=label,
                subtitle=subtitle,
                badge_text=version,
                notes=notes,
                icon_path=icon_path,
                badge_status=status,
            )
            self._nodes_items_layout.addWidget(card)

        self._nodes_items_layout.addStretch(1)

    def _populate_gizmos(self) -> None:
        _clear_layout(self._gizmos_items_layout)
        gizmo_files = _iter_runtime_files("gizmos")
        if not gizmo_files:
            empty = QtWidgets.QLabel("No gizmos are packaged in the current stable collection yet.")
            empty.setObjectName("EmptyState")
            self._gizmos_items_layout.addWidget(empty)
            return

        for path in gizmo_files:
            relative = path.relative_to(ROOT_DIR)
            card = AssetCardWidget(
                title=path.stem,
                subtitle="Gizmo package asset",
                badge_text=path.suffix.lower().lstrip(".") or "file",
                notes=str(relative).replace("\\", "/"),
                badge_status="hold",
            )
            self._gizmos_items_layout.addWidget(card)

        self._gizmos_items_layout.addStretch(1)

    def _populate_scripts(self) -> None:
        _clear_layout(self._scripts_items_layout)
        script_files = _iter_runtime_files("scripts")
        if not script_files:
            empty = QtWidgets.QLabel("No scripts are packaged in the current stable collection yet.")
            empty.setObjectName("EmptyState")
            self._scripts_items_layout.addWidget(empty)
            return

        for path in script_files:
            relative = path.relative_to(ROOT_DIR)
            card = AssetCardWidget(
                title=path.stem,
                subtitle="Script package asset",
                badge_text=path.suffix.lower().lstrip(".") or "file",
                notes=str(relative).replace("\\", "/"),
                badge_status="test",
            )
            self._scripts_items_layout.addWidget(card)

        self._scripts_items_layout.addStretch(1)

    def _refresh_update_summary(self) -> None:
        info = get_collection_info()
        current_collection_version = str(info.get("version", "unknown")).strip()

        if self._update_result is None:
            self._latest_version["value"].setText("Not checked")
            self._update_summary.setText(
                "No remote release has been checked yet. Use the button below to compare this install with the latest GitHub release."
            )
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

        self._latest_version["value"].setText(latest_version)
        self._update_channel.setText(channel)
        self._release_link.setText(notes_url or "No release notes URL available.")

        if available:
            self._update_summary.setText(
                f"TCollection {latest_version} is available. You are currently on {current_version}. {reason}"
            )
        else:
            self._update_summary.setText(
                f"TCollection {current_version} already matches the latest published release. {reason}"
            )

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
