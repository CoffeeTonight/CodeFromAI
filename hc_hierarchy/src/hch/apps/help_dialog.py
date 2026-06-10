"""PySide6 Help dialog for hch-gui."""

from __future__ import annotations

from hch.apps.help_text import ABOUT_TEXT, gui_help_sections


def show_help_dialog(parent=None, *, initial_tab: int = 0) -> None:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QTabWidget,
            QTextBrowser,
            QVBoxLayout,
        )
    except ImportError as e:
        raise SystemExit("PySide6 required: pip install -e '.[gui]'") from e

    dlg = QDialog(parent)
    dlg.setWindowTitle("hc_hierarchy Help")
    dlg.setFixedSize(780, 620)

    tabs = QTabWidget()
    tabs.setDocumentMode(True)
    for title, body in gui_help_sections():
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setPlainText(body)
        browser.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tabs.addTab(browser, title)

    if 0 <= initial_tab < tabs.count():
        tabs.setCurrentIndex(initial_tab)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dlg.reject)
    buttons.accepted.connect(dlg.accept)

    layout = QVBoxLayout(dlg)
    layout.addWidget(tabs, 1)
    layout.addWidget(buttons)
    dlg.exec()


def show_about_dialog(parent=None) -> None:
    try:
        from PySide6.QtWidgets import QMessageBox
    except ImportError as e:
        raise SystemExit("PySide6 required: pip install -e '.[gui]'") from e

    QMessageBox.about(parent, "About hc_hierarchy", ABOUT_TEXT)