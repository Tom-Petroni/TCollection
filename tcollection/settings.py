"""Qt settings dialog for TCollection."""

from __future__ import annotations

from typing import Any

import nuke  # ty: ignore[unresolved-import]

from .loader import get_collection_info, get_nodes, resolve_node_icon_path
from .updater import (
    check_for_updates,
    get_install_state,
    prepare_update_for_next_launch,
)

try:  # pragma: no cover - depends on the Nuke runtime
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - fallback for newer runtimes
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]


_SETTINGS_DIALOG: "TCollectionSettingsDialog | None" = None


class TCollectionSettingsDialog(QtWidgets.QDialog):
    """Central settings window for collection status and updates."""

    def __init__(self) -> None:
        super().__init__()
        self._update_result: dict[str, Any] | None = None
        self.setWindowTitle("TCollection Settings")
        self.setObjectName("TCollectionSettingsDialog")
        self.setMinimumSize(900, 640)
        self.setModal(False)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog#TCollectionSettingsDialog {
                background: #0f1318;
                color: #e9edf2;
            }
            QFrame#HeroCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #19222d,
                    stop: 1 #243445
                );
                border: 1px solid #35506b;
                border-radius: 18px;
            }
            QFrame#InfoCard {
                background: #171d24;
                border: 1px solid #2b3948;
                border-radius: 14px;
            }
            QLabel#HeroTitle {
                font-size: 28px;
                font-weight: 700;
                color: #f5f7fa;
            }
            QLabel#HeroSubtitle {
                font-size: 12px;
                color: #9fb1c2;
            }
            QLabel#SectionTitle {
                font-size: 15px;
                font-weight: 700;
                color: #f3f5f7;
            }
            QLabel#CardLabel {
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.04em;
                color: #8ea1b3;
                text-transform: uppercase;
            }
            QLabel#CardValue {
                font-size: 13px;
                color: #f1f4f7;
            }
            QLabel#StatusPill {
                background: #13283a;
                border: 1px solid #2d5b82;
                border-radius: 10px;
                color: #dbeeff;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
            }
            QTableWidget {
                background: #11171d;
                border: 1px solid #2b3948;
                border-radius: 14px;
                gridline-color: #26313c;
                selection-background-color: #1e3348;
                selection-color: #f6f8fb;
            }
            QHeaderView::section {
                background: #171f27;
                color: #aebdcb;
                border: none;
                border-bottom: 1px solid #2b3948;
                padding: 10px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton {
                background: #223243;
                color: #f3f6f8;
                border: 1px solid #35506b;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2b4056;
            }
            QPushButton:disabled {
                background: #182028;
                color: #607282;
                border-color: #24313d;
            }
            QPushButton#PrimaryButton {
                background: #be6d20;
                border-color: #d98c3e;
            }
            QPushButton#PrimaryButton:hover {
                background: #d47a23;
            }
            """
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        hero = QtWidgets.QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QtWidgets.QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(6)

        self._hero_title = QtWidgets.QLabel("TCollection")
        self._hero_title.setObjectName("HeroTitle")
        hero_layout.addWidget(self._hero_title)

        self._hero_subtitle = QtWidgets.QLabel(
            "Collection manager for nodes, versions, and updates."
        )
        self._hero_subtitle.setObjectName("HeroSubtitle")
        hero_layout.addWidget(self._hero_subtitle)

        self._hero_status = QtWidgets.QLabel("")
        self._hero_status.setObjectName("StatusPill")
        self._hero_status.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        hero_layout.addWidget(self._hero_status, 0, QtCore.Qt.AlignLeft)
        layout.addWidget(hero)

        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(14)
        layout.addLayout(cards_layout)

        collection_card = self._build_info_card("Collection")
        collection_form = QtWidgets.QFormLayout()
        collection_form.setContentsMargins(0, 0, 0, 0)
        collection_form.setSpacing(10)
        self._collection_version = self._build_value_label()
        self._managed_version = self._build_value_label()
        self._pending_version = self._build_value_label()
        self._runtime_root = self._build_value_label(word_wrap=True)
        collection_form.addRow(self._build_label("Collection Version"), self._collection_version)
        collection_form.addRow(self._build_label("Managed Version"), self._managed_version)
        collection_form.addRow(self._build_label("Pending Version"), self._pending_version)
        collection_form.addRow(self._build_label("Runtime Root"), self._runtime_root)
        collection_card.layout().addLayout(collection_form)
        cards_layout.addWidget(collection_card, 1)

        updates_card = self._build_info_card("Updates")
        updates_layout = updates_card.layout()
        self._update_summary = self._build_value_label(word_wrap=True)
        self._release_link = self._build_value_label(word_wrap=True)
        updates_layout.addWidget(self._build_label("Status"))
        updates_layout.addWidget(self._update_summary)
        updates_layout.addSpacing(6)
        updates_layout.addWidget(self._build_label("Release Notes"))
        updates_layout.addWidget(self._release_link)
        updates_layout.addSpacing(12)

        buttons_row = QtWidgets.QHBoxLayout()
        buttons_row.setSpacing(10)
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
        updates_layout.addLayout(buttons_row)
        cards_layout.addWidget(updates_card, 1)

        nodes_card = self._build_info_card("Installed Nodes")
        nodes_layout = nodes_card.layout()
        self._nodes_table = QtWidgets.QTableWidget(0, 3)
        self._nodes_table.setHorizontalHeaderLabels(["Node", "Version", "Status"])
        self._nodes_table.verticalHeader().setVisible(False)
        self._nodes_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._nodes_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._nodes_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._nodes_table.setAlternatingRowColors(False)
        self._nodes_table.setShowGrid(False)
        self._nodes_table.setIconSize(QtCore.QSize(20, 20))
        header = self._nodes_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        nodes_layout.addWidget(self._nodes_table)
        layout.addWidget(nodes_card, 1)

        footer_row = QtWidgets.QHBoxLayout()
        footer_row.addStretch(1)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.close)
        footer_row.addWidget(close_button)
        layout.addLayout(footer_row)

    def _build_info_card(self, title: str) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("InfoCard")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)
        return card

    def _build_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("CardLabel")
        return label

    def _build_value_label(self, word_wrap: bool = False) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel("")
        label.setObjectName("CardValue")
        label.setWordWrap(word_wrap)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        return label

    def refresh_all(self) -> None:
        self._refresh_collection_state()
        self._refresh_nodes_table()
        self._refresh_update_summary()

    def _refresh_collection_state(self) -> None:
        info = get_collection_info()
        state = get_install_state()
        self._hero_title.setText(str(info.get("display_name", "TCollection")))
        self._hero_subtitle.setText(
            f"Collection version {info.get('version', 'unknown')} ready inside Nuke."
        )
        self._hero_status.setText("Stable collection menu with managed updates")
        self._collection_version.setText(str(info.get("version", "unknown")))
        self._managed_version.setText(state.get("current_version", "") or "Not installed")
        self._pending_version.setText(state.get("pending_version", "") or "None")
        self._runtime_root.setText(state.get("runtime_root", ""))

    def _refresh_nodes_table(self) -> None:
        nodes = sorted(get_nodes(), key=lambda entry: str(entry.get("label", entry.get("key", ""))).lower())
        self._nodes_table.setRowCount(len(nodes))

        for row, entry in enumerate(nodes):
            label = str(entry.get("label", entry.get("key", ""))).strip()
            version = str(entry.get("version", "")).strip()
            status = str(entry.get("status", "")).strip()
            icon_path = resolve_node_icon_path(str(entry.get("key", "")).strip())

            label_item = QtWidgets.QTableWidgetItem(label)
            if icon_path:
                label_item.setIcon(QtGui.QIcon(icon_path))
            version_item = QtWidgets.QTableWidgetItem(version)
            status_item = QtWidgets.QTableWidgetItem(status)

            label_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            version_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            status_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)

            self._nodes_table.setItem(row, 0, label_item)
            self._nodes_table.setItem(row, 1, version_item)
            self._nodes_table.setItem(row, 2, status_item)

        self._nodes_table.resizeRowsToContents()

    def _refresh_update_summary(self) -> None:
        if self._update_result is None:
            self._update_summary.setText("Not checked yet. Use the button to query the latest GitHub release.")
            self._release_link.setText("No release notes loaded.")
            self._prepare_button.setEnabled(False)
            self._notes_button.setEnabled(False)
            return

        available = bool(self._update_result.get("available", False))
        latest_version = str(self._update_result.get("latest_version", "")).strip()
        current_version = str(self._update_result.get("current_version", "")).strip()
        reason = str(self._update_result.get("reason", "")).strip()
        notes_url = str(self._update_result.get("notes_url", "")).strip()

        if available:
            self._update_summary.setText(
                f"Update available: {current_version} -> {latest_version}\n{reason}"
            )
        else:
            self._update_summary.setText(
                f"{current_version} is current.\n{reason}"
            )

        self._release_link.setText(notes_url or "No release notes URL available.")
        self._prepare_button.setEnabled(available)
        self._notes_button.setEnabled(bool(notes_url))

    def _check_for_updates(self) -> None:
        self._check_button.setEnabled(False)
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self._update_result = check_for_updates()
        except Exception as exc:
            self._update_result = {
                "available": False,
                "current_version": get_collection_info().get("version", "unknown"),
                "latest_version": get_collection_info().get("version", "unknown"),
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
            f"Update prepared: {result['version']}\nRestart Nuke to activate it."
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
