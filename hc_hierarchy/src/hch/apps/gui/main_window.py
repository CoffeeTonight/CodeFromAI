"""Lazy hierarchy tree + DQL bar over SQLite index."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

from hch.apps.help_dialog import show_about_dialog, show_help_dialog
from hch.query.dql.planner import apply_post_filters, plan_dql
from hch.query.dql.results import format_rows_text


_TIER_USER_ROLE = 1  # Qt.ItemDataRole.UserRole + 1


def tier_can_deepen(tier: str) -> bool:
    return tier in ("skim", "shallow_cap")


def _parse_tier_from_tags(raw: Optional[str]) -> str:
    if not raw:
        return "full"
    import json

    try:
        tags = json.loads(raw)
    except json.JSONDecodeError:
        return "full"
    if isinstance(tags, dict):
        return str(tags.get("parse_tier") or "full")
    return "full"


def _query_children(conn: sqlite3.Connection, parent_path: Optional[str]) -> List[Tuple]:
    if parent_path is None:
        cur = conn.execute(
            """
            SELECT full_path, inst_leaf_name, module_id, depth, inst_tags_json
            FROM instances
            WHERE parent_path IS NULL OR parent_path = ''
            ORDER BY full_path
            """
        )
    else:
        cur = conn.execute(
            """
            SELECT full_path, inst_leaf_name, module_id, depth, inst_tags_json
            FROM instances
            WHERE parent_path = ?
            ORDER BY full_path
            """,
            (parent_path,),
        )
    return cur.fetchall()


def _module_name(conn: sqlite3.Connection, module_id: int) -> str:
    row = conn.execute(
        "SELECT module_name FROM modules WHERE id = ?", (module_id,)
    ).fetchone()
    return row[0] if row else "?"


def run_gui(db_path: str) -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QAction, QKeySequence
        from PySide6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMenuBar,
            QPushButton,
            QSplitter,
            QTableWidget,
            QTableWidgetItem,
            QTreeWidget,
            QTreeWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as e:
        raise SystemExit(
            "PySide6 required for GUI: pip install -e '.[gui]'"
        ) from e

    db = Path(db_path).resolve()
    if not db.exists():
        raise SystemExit(f"Database not found: {db}")

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(f"hc_hierarchy — {db.name}")
            self.conn = sqlite3.connect(str(db))
            self.conn.row_factory = sqlite3.Row
            self._db_path = db
            self._last_query = ""
            self._last_export_text = ""
            self._build_menus()

            splitter = QSplitter()
            self.tree = QTreeWidget()
            self.tree.setHeaderLabels(["Instance", "Module"])
            self.tree.itemExpanded.connect(self._on_expand)
            self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._tree_context_menu)
            self.tree.itemSelectionChanged.connect(self._sync_deepen_action)
            splitter.addWidget(self.tree)

            right = QWidget()
            rv = QVBoxLayout(right)
            qrow = QHBoxLayout()
            self.qedit = QLineEdit()
            self.qedit.setPlaceholderText(
                'path ~ "top.u_*"  ·  inst ~ "u_*"  ·  module ~ "uart*"  ·  F1=Help'
            )
            self.qedit.returnPressed.connect(self._run_query)
            qbtn = QPushButton("Run")
            qbtn.setToolTip("Run DQL query (Enter)")
            qbtn.clicked.connect(self._run_query)
            help_btn = QPushButton("?")
            help_btn.setToolTip("DQL help (F1)")
            help_btn.setFixedWidth(28)
            help_btn.clicked.connect(lambda: show_help_dialog(self, initial_tab=1))
            text_btn = QPushButton("Text")
            text_btn.setToolTip("Copy results as text")
            text_btn.clicked.connect(self._copy_results_text)
            save_btn = QPushButton("↓")
            save_btn.setToolTip("Save results to file…")
            save_btn.setFixedWidth(32)
            save_btn.clicked.connect(self._save_results_text)
            qrow.addWidget(QLabel("DQL"))
            qrow.addWidget(self.qedit, 1)
            qrow.addWidget(qbtn)
            qrow.addWidget(text_btn)
            qrow.addWidget(save_btn)
            qrow.addWidget(help_btn)
            rv.addLayout(qrow)
            self.table = QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["full_path", "module", "file", "depth"])
            rv.addWidget(self.table, 1)
            splitter.addWidget(right)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)
            self.setCentralWidget(splitter)
            self.statusBar().showMessage(
                "Gold=skim, orange=depth cap, purple=blackbox — Deepen on skim/cap (Ctrl+D)"
            )
            self._load_roots()

        def _build_menus(self) -> None:
            bar = QMenuBar(self)
            self.setMenuBar(bar)

            file_menu = bar.addMenu("File")
            act_save = QAction("Save Query Results…", self)
            act_save.setShortcut("Ctrl+S")
            act_save.triggered.connect(self._save_results_text)
            file_menu.addAction(act_save)
            act_copy = QAction("Copy Query Results", self)
            act_copy.setShortcut("Ctrl+Shift+C")
            act_copy.triggered.connect(self._copy_results_text)
            file_menu.addAction(act_copy)

            help_menu = bar.addMenu("Help")
            act_guide = QAction("User Guide…", self)
            act_guide.setShortcut(QKeySequence(QKeySequence.StandardKey.HelpContents))
            act_guide.triggered.connect(lambda: show_help_dialog(self))
            help_menu.addAction(act_guide)

            act_dql = QAction("DQL Syntax…", self)
            act_dql.setShortcut("F1")
            act_dql.triggered.connect(lambda: show_help_dialog(self, initial_tab=1))
            help_menu.addAction(act_dql)

            help_menu.addSeparator()

            act_index = QAction("Indexing (hch-index)…", self)
            act_index.triggered.connect(lambda: show_help_dialog(self, initial_tab=2))
            help_menu.addAction(act_index)

            act_query = QAction("Batch Query (hch-query)…", self)
            act_query.triggered.connect(lambda: show_help_dialog(self, initial_tab=3))
            help_menu.addAction(act_query)

            tree_menu = bar.addMenu("Tree")
            self.act_deepen = QAction("Deepen Branch…", self)
            self.act_deepen.setShortcut("Ctrl+D")
            self.act_deepen.setToolTip(
                "Re-parse shallow/text-skim branch with pyslang (full subtree)"
            )
            self.act_deepen.triggered.connect(self._deepen_selected)
            self.act_deepen.setEnabled(False)
            tree_menu.addAction(self.act_deepen)

            help_menu.addSeparator()

            act_about = QAction("About…", self)
            act_about.triggered.connect(lambda: show_about_dialog(self))
            help_menu.addAction(act_about)

        def _apply_tier_style(self, item: QTreeWidgetItem, tier: str) -> None:
            from PySide6.QtGui import QColor

            if tier == "skim":
                fg = QColor("#e8d48a")
                item.setForeground(0, fg)
                item.setForeground(1, QColor("#a89050"))
            elif tier == "shallow_cap":
                fg = QColor("#e8b89a")
                item.setForeground(0, fg)
                item.setForeground(1, QColor("#a87858"))
            elif tier == "blackbox":
                fg = QColor("#9b8fe0")
                item.setForeground(0, fg)
                item.setForeground(1, QColor("#7a6eb8"))

        def _make_item(
            self, full_path: str, leaf: str, mod: str, *, parse_tier: str = "full"
        ) -> QTreeWidgetItem:
            item = QTreeWidgetItem([leaf, mod])
            item.setData(0, Qt.ItemDataRole.UserRole, full_path)
            item.setData(0, Qt.ItemDataRole.UserRole + _TIER_USER_ROLE, parse_tier)
            self._apply_tier_style(item, parse_tier)
            if tier_can_deepen(parse_tier):
                tip = (
                    f"{full_path}\n"
                    "Text-skim / depth cap — right-click or Tree → Deepen Branch"
                )
                item.setToolTip(0, tip)
                item.setToolTip(1, tip)
            item.addChild(QTreeWidgetItem(["…", ""]))
            return item

        def _selected_tree_item(self) -> Optional[QTreeWidgetItem]:
            items = self.tree.selectedItems()
            return items[0] if items else None

        def _tier_for_item(self, item: Optional[QTreeWidgetItem]) -> str:
            if not item:
                return "full"
            tier = item.data(0, Qt.ItemDataRole.UserRole + _TIER_USER_ROLE)
            return str(tier or "full")

        def _sync_deepen_action(self) -> None:
            item = self._selected_tree_item()
            self.act_deepen.setEnabled(tier_can_deepen(self._tier_for_item(item)))

        def _tree_context_menu(self, pos) -> None:
            from PySide6.QtWidgets import QMenu

            item = self.tree.itemAt(pos)
            if not item:
                return
            self.tree.setCurrentItem(item)
            if not tier_can_deepen(self._tier_for_item(item)):
                return
            menu = QMenu(self)
            act = menu.addAction("Deepen branch (pyslang, full subtree)")
            act.triggered.connect(self._deepen_selected)
            menu.exec(self.tree.viewport().mapToGlobal(pos))

        def _deepen_selected(self) -> None:
            item = self._selected_tree_item()
            if not item:
                return
            full_path = item.data(0, Qt.ItemDataRole.UserRole)
            if not full_path or not tier_can_deepen(self._tier_for_item(item)):
                return
            self._deepen_branch(str(full_path))

        def _deepen_branch(self, full_path: str) -> None:
            from hch.engine.availability import check_engine
            from hch.index.deepen import deepen_branch

            status = check_engine()
            if not status.available:
                self.statusBar().showMessage(f"Deepen failed: {status.message}")
                return

            self.act_deepen.setEnabled(False)
            self.statusBar().showMessage(f"Deepening {full_path}…")
            QApplication.processEvents()
            try:
                result = deepen_branch(
                    str(self._db_path),
                    full_path,
                    full_subtree=True,
                    on_phase=lambda msg: self.statusBar().showMessage(msg),
                )
            except (ValueError, OSError, RuntimeError) as exc:
                self.statusBar().showMessage(f"Deepen failed: {exc}")
                self._sync_deepen_action()
                return

            self._reload_tree_expand(full_path)
            self.statusBar().showMessage(
                f"Deepened {full_path}: "
                f"{result.instances_before} → {result.instances_after} instances"
            )
            self._sync_deepen_action()

        def _load_children(self, item: QTreeWidgetItem) -> None:
            if item.childCount() != 1 or item.child(0).text(0) != "…":
                return
            item.takeChildren()
            full_path = item.data(0, Qt.ItemDataRole.UserRole)
            for row in _query_children(self.conn, full_path):
                fp, leaf, mid, _depth, tags = row
                mod = _module_name(self.conn, mid)
                tier = _parse_tier_from_tags(tags)
                item.addChild(self._make_item(fp, leaf, mod, parse_tier=tier))

        def _reload_tree_expand(self, target_path: str) -> None:
            self._load_roots()
            if not target_path:
                return

            def walk(item: QTreeWidgetItem) -> bool:
                fp = item.data(0, Qt.ItemDataRole.UserRole)
                if not fp:
                    return False
                if target_path == fp:
                    self.tree.setCurrentItem(item)
                    self.tree.scrollToItem(item)
                    return True
                if not target_path.startswith(f"{fp}."):
                    return False
                self._load_children(item)
                item.setExpanded(True)
                for i in range(item.childCount()):
                    if walk(item.child(i)):
                        return True
                return False

            for i in range(self.tree.topLevelItemCount()):
                if walk(self.tree.topLevelItem(i)):
                    return

        def _load_roots(self) -> None:
            self.tree.clear()
            for row in _query_children(self.conn, None):
                fp, leaf, mid, _depth, tags = row
                mod = _module_name(self.conn, mid)
                tier = _parse_tier_from_tags(tags)
                self.tree.addTopLevelItem(self._make_item(fp, leaf, mod, parse_tier=tier))

        def _on_expand(self, item: QTreeWidgetItem) -> None:
            self._load_children(item)

        def _copy_results_text(self) -> None:
            if not self._last_export_text:
                self.statusBar().showMessage("Run a DQL query first")
                return
            QApplication.clipboard().setText(self._last_export_text)
            self.statusBar().showMessage("Copied to clipboard")

        def _save_results_text(self) -> None:
            from PySide6.QtWidgets import QFileDialog

            if not self._last_export_text:
                self.statusBar().showMessage("Run a DQL query first")
                return
            default_name = f"{self._db_path.stem}-query-results.txt"
            default_path = str(self._db_path.parent / default_name)
            path, _selected = QFileDialog.getSaveFileName(
                self,
                "Save Query Results",
                default_path,
                "Text (*.txt *.tsv);;All files (*)",
            )
            if not path:
                return
            Path(path).write_text(self._last_export_text, encoding="utf-8")
            self.statusBar().showMessage(f"Saved: {path}")

        def _run_query(self) -> None:
            q = self.qedit.text().strip()
            if not q:
                return
            plan = plan_dql(q)
            rows = [
                dict(r)
                for r in self.conn.execute(plan.sql, plan.params).fetchall()
            ]
            rows = apply_post_filters(rows, plan)
            self._last_query = q
            self._last_export_text = format_rows_text(rows, query=q)
            self.statusBar().showMessage(f"DQL: {len(rows)} rows — {q}")
            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.table.setItem(i, 0, QTableWidgetItem(r.get("full_path", "")))
                self.table.setItem(i, 1, QTableWidgetItem(r.get("module_name", "")))
                self.table.setItem(i, 2, QTableWidgetItem(r.get("filepath") or ""))
                self.table.setItem(i, 3, QTableWidgetItem(str(r.get("depth", ""))))

        def closeEvent(self, event) -> None:
            self.conn.close()
            super().closeEvent(event)

    app = QApplication([])
    win = MainWindow()
    win.resize(1100, 700)
    win.show()
    return app.exec()


def main(argv=None) -> int:
    import argparse

    from hch.apps.help_text import GUI_HELP_EPILOG

    ap = argparse.ArgumentParser(
        description="hc_hierarchy desktop GUI (hierarchy explorer + on-demand deepen)",
        epilog=GUI_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-d", "--database", required=True, help="SQLite .hch.db path")
    args = ap.parse_args(argv)
    return run_gui(args.database)


if __name__ == "__main__":
    import sys

    sys.exit(main())