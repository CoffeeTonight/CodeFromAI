"""Lazy hierarchy tree + DQL bar over SQLite index."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

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
        from PySide6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
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

            splitter = QSplitter()
            self.tree = QTreeWidget()
            self.tree.setHeaderLabels(["Instance", "Module"])
            self.tree.itemExpanded.connect(self._on_expand)
            splitter.addWidget(self.tree)

            right = QWidget()
            rv = QVBoxLayout(right)
            qrow = QHBoxLayout()
            self.qedit = QLineEdit()
            self.qedit.setPlaceholderText('DQL e.g. module ~ "uart*"')
            qbtn = QPushButton("Run")
            qbtn.clicked.connect(self._run_query)
            qrow.addWidget(QLabel("DQL"))
            qrow.addWidget(self.qedit, 1)
            qrow.addWidget(qbtn)
            rv.addLayout(qrow)
            self.table = QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["full_path", "module", "file", "depth"])
            rv.addWidget(self.table, 1)
            splitter.addWidget(right)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)
            self.setCentralWidget(splitter)
            self._load_roots()

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

    ap = argparse.ArgumentParser(description="hc_hierarchy GUI")
    ap.add_argument("-d", "--database", required=True, help="SQLite .hch.db")
    args = ap.parse_args(argv)
    return run_gui(args.database)