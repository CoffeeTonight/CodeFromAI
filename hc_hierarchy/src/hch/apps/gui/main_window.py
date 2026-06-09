"""Lazy hierarchy tree + DQL bar over SQLite index."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

from hch.apps.help_dialog import show_about_dialog, show_help_dialog
from hch.query.dql.planner import apply_post_filters, plan_dql


def _query_children(conn: sqlite3.Connection, parent_path: Optional[str]) -> List[Tuple]:
    if parent_path is None:
        cur = conn.execute(
            """
            SELECT full_path, inst_leaf_name, module_id, depth
            FROM instances
            WHERE parent_path IS NULL OR parent_path = ''
            ORDER BY full_path
            """
        )
    else:
        cur = conn.execute(
            """
            SELECT full_path, inst_leaf_name, module_id, depth
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
            self._build_menus()

            splitter = QSplitter()
            self.tree = QTreeWidget()
            self.tree.setHeaderLabels(["Instance", "Module"])
            self.tree.itemExpanded.connect(self._on_expand)
            splitter.addWidget(self.tree)

            right = QWidget()
            rv = QVBoxLayout(right)
            qrow = QHBoxLayout()
            self.qedit = QLineEdit()
            self.qedit.setPlaceholderText(
                'path ~ "top.u_*"  ·  inst ~ "u_*"  ·  module ~ "uart*"  ·  F1=도움말'
            )
            self.qedit.returnPressed.connect(self._run_query)
            qbtn = QPushButton("Run")
            qbtn.setToolTip("Run DQL query (Enter)")
            qbtn.clicked.connect(self._run_query)
            help_btn = QPushButton("?")
            help_btn.setToolTip("DQL 도움말 (F1)")
            help_btn.setFixedWidth(28)
            help_btn.clicked.connect(lambda: show_help_dialog(self, initial_tab=1))
            qrow.addWidget(QLabel("DQL"))
            qrow.addWidget(self.qedit, 1)
            qrow.addWidget(qbtn)
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
                "도움말: 메뉴 [도움말] 또는 F1 — inst=leaf이름, path=전체경로"
            )
            self._load_roots()

        def _build_menus(self) -> None:
            bar = QMenuBar(self)
            self.setMenuBar(bar)

            help_menu = bar.addMenu("도움말")
            act_guide = QAction("사용 가이드…", self)
            act_guide.setShortcut(QKeySequence(QKeySequence.StandardKey.HelpContents))
            act_guide.triggered.connect(lambda: show_help_dialog(self))
            help_menu.addAction(act_guide)

            act_dql = QAction("DQL 검색 문법…", self)
            act_dql.setShortcut("F1")
            act_dql.triggered.connect(lambda: show_help_dialog(self, initial_tab=1))
            help_menu.addAction(act_dql)

            help_menu.addSeparator()

            act_index = QAction("인덱싱 (hch-index)…", self)
            act_index.triggered.connect(lambda: show_help_dialog(self, initial_tab=2))
            help_menu.addAction(act_index)

            act_query = QAction("배치 쿼리 (hch-query)…", self)
            act_query.triggered.connect(lambda: show_help_dialog(self, initial_tab=3))
            help_menu.addAction(act_query)

            help_menu.addSeparator()

            act_about = QAction("정보…", self)
            act_about.triggered.connect(lambda: show_about_dialog(self))
            help_menu.addAction(act_about)

        def _make_item(self, full_path: str, leaf: str, mod: str) -> QTreeWidgetItem:
            item = QTreeWidgetItem([leaf, mod])
            item.setData(0, Qt.ItemDataRole.UserRole, full_path)
            item.addChild(QTreeWidgetItem(["…", ""]))
            return item

        def _load_roots(self) -> None:
            self.tree.clear()
            for row in _query_children(self.conn, None):
                fp, leaf, mid, _depth = row
                mod = _module_name(self.conn, mid)
                self.tree.addTopLevelItem(self._make_item(fp, leaf, mod))

        def _on_expand(self, item: QTreeWidgetItem) -> None:
            if item.childCount() != 1:
                return
            if item.child(0).text(0) != "…":
                return
            item.takeChildren()
            full_path = item.data(0, Qt.ItemDataRole.UserRole)
            for row in _query_children(self.conn, full_path):
                fp, leaf, mid, _depth = row
                mod = _module_name(self.conn, mid)
                item.addChild(self._make_item(fp, leaf, mod))

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
        description="hc_hierarchy desktop GUI (read-only hierarchy explorer)",
        epilog=GUI_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-d", "--database", required=True, help="SQLite .hch.db path")
    args = ap.parse_args(argv)
    return run_gui(args.database)


if __name__ == "__main__":
    import sys

    sys.exit(main())