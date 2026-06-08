#!/usr/bin/env python3
"""
rtl_dql_gui.py - RTL DQL Interactive Explorer (PySide6)

Full implementation covering:
- A: DQL query + results table
- B: Left hierarchy tree with keyboard navigation (→ ← expand/collapse)
- D: Click result → detail + right Source File Viewer
- F: Load .txt query files (batch style)
- E: Query history
- Tree + search integration (highlight matching nodes)
"""

import sys
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QCheckBox, QTableWidget, QTableWidgetItem,
    QSplitter, QLabel, QTextEdit, QStatusBar, QTreeView, QFileDialog,
    QComboBox, QMessageBox, QListWidget, QListWidgetItem, QProgressBar, QPlainTextEdit,
    QHeaderView
)
from PySide6.QtCore import Qt, QModelIndex, QThread, Signal, QObject
from PySide6.QtGui import (
    QFont, QStandardItemModel, QStandardItem, QTextCursor,
    QTextCharFormat, QBrush, QColor, QKeySequence, QShortcut
)

# Project root — prefer installed rvast; else src/ for development
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from rvast.dql import query_dql
    from rvast.filelist.eda import EDAFilelistParser
    from rvast.pipeline import PipelineConfig, run_from_filelist
    from rvast.schema import Instance
except ImportError:
    # Fallback when package not installed (dev: pip install -e .)
    try:
        from tools.dql_python import query_dql
        from tools.eda_filelist_parser import EDAFilelistParser
        from rvast.pipeline import PipelineConfig, run_from_filelist  # type: ignore
        from rvast.schema import Instance  # type: ignore
    except ImportError:
        query_dql = None
        EDAFilelistParser = None
        run_from_filelist = None
        PipelineConfig = None
        Instance = None


class FilelistParseWorker(QObject):
    """파일리스트 파싱을 백그라운드에서 수행 (UI 멈춤 방지)"""
    progress = Signal(int, str)
    finished = Signal(object)  # EDAFilelistParser or None

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            from rvast.filelist.eda import EDAFilelistParser
            self.progress.emit(10, "Parsing filelist...")

            parser = EDAFilelistParser(self.file_path)

            self.progress.emit(90, f"Found {len(parser.source_files)} files")
            self.finished.emit(parser)

        except Exception as e:
            print(f"Filelist parse error: {e}")
            self.finished.emit(None)


class ElaborationWorker(QObject):
    """Filelist을 받아 hierarchy를 추출하는 작업을 백그라운드에서 수행."""
    progress = Signal(int, str)      # (percentage, message)
    finished = Signal(bool, str, list)  # (success, message, hierarchy_data)

    def __init__(self, parser: "EDAFilelistParser"):
        super().__init__()
        self.parser = parser

    def run(self):
        try:
            if run_from_filelist is None:
                self.finished.emit(False, "rvast package not installed. Run: pip install -e .", [])
                return

            top_f = str(self.parser.top_filelist) if hasattr(self.parser, "top_filelist") else None
            if not top_f:
                self.finished.emit(False, "Filelist path unknown on parser.", [])
                return

            def on_progress(pct: int, msg: str) -> None:
                self.progress.emit(pct, msg)

            result = run_from_filelist(
                top_f,
                config=PipelineConfig() if PipelineConfig else None,
                progress=on_progress,
            )
            hierarchy_data = result.to_dict_list()
            if hierarchy_data:
                msg = (
                    f"Extracted {len(hierarchy_data)} instance(s) "
                    f"via Python pipeline (mode={result.mode_used})."
                )
                self.finished.emit(True, msg, hierarchy_data)
            else:
                err = "; ".join(result.errors[:3]) if result.errors else "No instances"
                self.finished.emit(False, f"Elaboration produced no instances. {err}", [])

        except Exception as e:
            self.finished.emit(False, str(e), [])


def build_hierarchy_tree_model(instances: List[Dict[str, Any]]) -> QStandardItemModel:
    """Build a QStandardItemModel tree from dot-separated hierarchy names."""
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Hierarchy"])

    root = model.invisibleRootItem()
    node_map: Dict[str, QStandardItem] = {}

    for inst in instances:
        name = inst.get("name", "")
        if not name:
            continue

        parts = name.split(".")
        current_path = ""
        parent = root

        for i, part in enumerate(parts):
            current_path = current_path + "." + part if current_path else part

            if current_path not in node_map:
                item = QStandardItem(part)
                item.setEditable(False)
                # Store full path in data role
                item.setData(current_path, Qt.UserRole + 1)
                item.setData(inst, Qt.UserRole + 2)  # store original instance data
                parent.appendRow(item)
                node_map[current_path] = item

            parent = node_map[current_path]

    return model


class RtlDqlGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("rtl_dql - RTL DQL Explorer")
        self.resize(1500, 920)

        self.current_data: List[Dict[str, Any]] = []
        self.default_data_path = PROJECT_ROOT / "demo_data" / "tiny_soc.json"
        self.query_history: List[str] = []
        self.last_results: List[Dict] = []
        self.source_root: Optional[Path] = None   # User can set this to their RTL directory
        self.current_filelist: Optional["EDAFilelistParser"] = None

        # Remember last accessed directories for file dialogs (human-friendly UX)
        self.last_filelist_dir: Optional[str] = None
        self.last_query_dir: Optional[str] = None

        self._setup_ui()
        self._load_default_data()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # === Top control bar ===
        control_layout = QHBoxLayout()

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText('module ~ "uart" AND port ~ "irq"   (Enter to run)')
        self.query_input.returnPressed.connect(self.run_query)

        self.run_btn = QPushButton("Run Query")
        self.run_btn.clicked.connect(self.run_query)

        self.port_mode_cb = QCheckBox("Port Mode (B-mode)")
        self.port_mode_cb.setChecked(True)

        # Buttons in logical workflow order: Filelist → Elaborate → Query Load
        self.open_filelist_btn = QPushButton("Open Filelist...")
        self.open_filelist_btn.setObjectName("btn_filelist")
        self.open_filelist_btn.clicked.connect(self.open_filelist)

        self.elaborate_btn = QPushButton("Elaborate")
        self.elaborate_btn.setObjectName("btn_elaborate")
        self.elaborate_btn.setEnabled(False)
        self.elaborate_btn.clicked.connect(self.start_elaboration)

        self.load_queries_btn = QPushButton("Load .txt Queries...")
        self.load_queries_btn.setObjectName("btn_query")
        self.load_queries_btn.clicked.connect(self.load_query_file)

        self.export_md_btn = QPushButton("Export Results to MD")
        self.export_md_btn.setObjectName("btn_export")
        self.export_md_btn.clicked.connect(self.export_results_to_md)

        self.history_combo = QComboBox()
        self.history_combo.setMinimumWidth(280)
        self.history_combo.setPlaceholderText("Query History")
        self.history_combo.currentTextChanged.connect(self._on_history_selected)

        control_layout.addWidget(QLabel("DQL:"))
        control_layout.addWidget(self.query_input, 1)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.port_mode_cb)
        # Layout order: Filelist → Elaborate → Query Load (at the end)
        control_layout.addWidget(self.open_filelist_btn)
        control_layout.addWidget(self.elaborate_btn)
        control_layout.addWidget(self.load_queries_btn)
        control_layout.addWidget(self.export_md_btn)
        control_layout.addWidget(QLabel("History:"))
        control_layout.addWidget(self.history_combo)

        main_layout.addLayout(control_layout)

        # === 3-Pane Main Splitter ===
        main_splitter = QSplitter(Qt.Horizontal)

        # === LEFT: Hierarchy Tree (Phase B) ===
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(4, 4, 4, 4)

        tree_label = QLabel("Hierarchy Tree (Keyboard: → ← to expand/collapse)")
        tree_label.setStyleSheet("font-weight: bold; color: #ccc;")
        left_layout.addWidget(tree_label)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setExpandsOnDoubleClick(True)
        self.tree_view.setSelectionMode(QTreeView.SingleSelection)

        # 긴 hierarchy 이름을 위한 horizontal scroll 지원
        self.tree_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree_view.setTextElideMode(Qt.ElideNone)  # ...으로 자르지 않음
        header = self.tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 내용에 맞게 초기 크기

        # Excellent default keyboard support for expand/collapse
        self.tree_view.setModel(QStandardItemModel())  # placeholder
        self.tree_view.selectionModel().selectionChanged.connect(self._on_tree_selection_changed)
        self.tree_view.doubleClicked.connect(self._on_tree_double_clicked)
        self._highlighted_tree_item = None  # 현재 노랑 강조된 트리 아이템

        left_layout.addWidget(self.tree_view)
        left_container.setMinimumWidth(380)  # 긴 이름 때문에 horizontal scroll을 위해 조금 더 넓게
        main_splitter.addWidget(left_container)

        # === CENTER: Results Table ===
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(4, 4, 4, 4)

        self.results_label = QLabel("Search Results")
        self.results_label.setStyleSheet("font-weight: bold;")
        center_layout.addWidget(self.results_label)

        # Full Hierarchy: 엑셀처럼 표 형태지만, 모든 행을 어두운 배경으로 통일 (가독성)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(1)
        self.results_table.setHorizontalHeaderLabels(["Full Hierarchy"])
        self.results_table.setAlternatingRowColors(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setStyleSheet("""
            QTableWidget {
                background-color: #252535;
                color: #ddd;
                gridline-color: #444;
            }
            QTableWidget::item {
                background-color: #252535;
                color: #ddd;
            }
            QTableWidget::item:selected {
                background-color: #3a4a7a;
            }
            QHeaderView::section {
                background-color: #2f2f42;
                color: white;
            }
        """)

        # 긴 hierarchy를 위한 horizontal scroll 강제 활성화
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(False)          # 컬럼이 자동으로 늘어나지 않게
        header.setMinimumSectionSize(1200)           # 초기 최소 너비 크게
        self.results_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.results_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

        self.results_table.itemSelectionChanged.connect(self._on_results_table_selected)
        self.results_table.doubleClicked.connect(self._on_results_table_double_clicked)
        self.results_table.setMinimumWidth(520)

        center_layout.addWidget(self.results_table)
        main_splitter.addWidget(center_container)

        # === RIGHT: Source File Viewer (Phase D) ===
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(4, 4, 4, 4)

        right_top = QHBoxLayout()
        right_label = QLabel("Source File Viewer")
        right_label.setStyleSheet("font-weight: bold;")
        # Set RTL Root 버튼은 제거 (더블클릭으로 자동 해결하도록 변경)
        # self.set_source_root_btn = QPushButton("Set RTL Root...")
        # self.set_source_root_btn.clicked.connect(self._choose_source_root)
        # self.set_source_root_btn.setMaximumWidth(120)

        right_top.addWidget(right_label)
        right_top.addStretch()
        # Set RTL Root 버튼 제거됨 (더블클릭 자동 해결)

        self.source_path_label = QLabel("(No file selected)")
        self.source_path_label.setStyleSheet("color: #888; font-size: 11px;")

        # Progress UI for elaboration (shown only during Elab)
        self.elab_progress = QProgressBar()
        self.elab_progress.setMaximum(100)
        self.elab_progress.hide()

        self.elab_log = QTextEdit()
        self.elab_log.setReadOnly(True)
        self.elab_log.setMaximumHeight(90)
        self.elab_log.hide()

        # List of files from the loaded filelist (interactive)
        self.filelist_list = QListWidget()
        self.filelist_list.setMaximumHeight(160)
        self.filelist_list.itemClicked.connect(self._on_filelist_file_clicked)
        self.filelist_list.hide()

        self.source_viewer = QTextEdit()
        self.source_viewer.setReadOnly(True)
        self.source_viewer.setFont(QFont("Monospace", 10))
        self.source_viewer.setLineWrapMode(QTextEdit.NoWrap)
        # 기본 글자색은 흰색
        self.source_viewer.setStyleSheet("QTextEdit { color: #ffffff; background-color: #1e1e2e; }")

        right_layout.addLayout(right_top)
        right_layout.addWidget(self.source_path_label)
        right_layout.addWidget(self.elab_progress)
        right_layout.addWidget(self.elab_log)
        right_layout.addWidget(self.filelist_list)
        right_layout.addWidget(self.source_viewer, 1)

        # Source Viewer 내장 Find 바 (Vim 스타일: 해당 글자만 빨간색으로 강조)
        find_bar = QWidget()
        find_layout = QHBoxLayout(find_bar)
        find_layout.setContentsMargins(4, 2, 4, 2)

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find (Enter: next, Shift+Enter: prev)")
        self.find_edit.returnPressed.connect(lambda: self._source_find_next())

        btn_next = QPushButton("Next")
        btn_next.clicked.connect(lambda: self._source_find_next(forward=True))

        btn_prev = QPushButton("Prev")
        btn_prev.clicked.connect(lambda: self._source_find_next(forward=False))

        btn_close = QPushButton("✕")
        btn_close.setMaximumWidth(30)
        btn_close.clicked.connect(lambda: self.find_edit.clear())

        find_layout.addWidget(QLabel("Find:"))
        find_layout.addWidget(self.find_edit, 1)
        find_layout.addWidget(btn_prev)
        find_layout.addWidget(btn_next)
        find_layout.addWidget(btn_close)

        right_layout.addWidget(find_bar)

        right_container.setMinimumWidth(380)
        main_splitter.addWidget(right_container)

        # Find 관련 상태
        self._find_matches = []
        self._current_find_index = -1

        # 검색어 변경 시 자동 하이라이트
        self.find_edit.textChanged.connect(self._on_find_text_changed)

        # Ctrl+F 로 Find 바 포커스
        shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(lambda: self.find_edit.setFocus())
        shortcut.activated.connect(lambda: self.find_edit.selectAll())

        main_splitter.setSizes([340, 580, 420])
        main_layout.addWidget(main_splitter, 1)

        # Status
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Use 'Open Filelist...' to load your analysis target .f file.")

    # ==================== Data Loading ====================

    def _load_default_data(self):
        try:
            with open(self.default_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "instances" in data:
                data = data["instances"]
            self.current_data = data if isinstance(data, list) else []
            self._rebuild_tree()
            self.status_bar.showMessage(f"Loaded {len(self.current_data)} instances from tiny_soc.json")
        except Exception as e:
            self.status_bar.showMessage(f"Failed to load default data: {e}")
            self.current_data = []

    def _rebuild_tree(self):
        if not self.current_data:
            return
        model = build_hierarchy_tree_model(self.current_data)
        self.tree_view.setModel(model)
        self.tree_view.expandToDepth(1)  # initial expansion

        # 긴 hierarchy 이름을 위해 컬럼 너비 확보 (horizontal scroll 유도)
        header = self.tree_view.header()
        header.setStretchLastSection(False)
        # 내용 기반으로 넓게 + 최소 보장
        self.tree_view.resizeColumnToContents(0)
        current_w = self.tree_view.columnWidth(0)
        self.tree_view.setColumnWidth(0, max(current_w, 900))

    # ==================== Query Execution ====================

    def run_query(self):
        if not self.current_data:
            QMessageBox.warning(self, "No Data", "No design data loaded.")
            return
        if query_dql is None:
            QMessageBox.critical(self, "Engine Error", "DQL engine (tools.dql_python) could not be imported.")
            return

        query = self.query_input.text().strip()
        if not query:
            self.status_bar.showMessage("Please enter a DQL query")
            return

        port_mode = self.port_mode_cb.isChecked()

        try:
            results = query_dql(query, self.current_data, port_mode=port_mode)
        except Exception as e:
            self.status_bar.showMessage(f"Query failed: {e}")
            return

        self.last_results = results
        self._populate_results_table(results, port_mode)
        self._highlight_tree_matches(results)

        # History
        if query not in self.query_history:
            self.query_history.insert(0, query)
            if len(self.query_history) > 15:
                self.query_history.pop()
            self._refresh_history_combo()

        self.status_bar.showMessage(f"Query: {query}  |  {len(results)} results  |  PortMode={port_mode}")

    def _populate_results_table(self, results: List[Dict], port_mode: bool):
        """Full Hierarchy: 한 줄에 hierarchy 하나 (포트 매칭 시 .port까지 포함)"""
        self.results_table.setRowCount(0)
        self.results_data = results

        for row_idx, item in enumerate(results):
            self.results_table.insertRow(row_idx)

            name = item.get("name") or item.get("hierarchy") or ""
            port = item.get("_port", "")

            if port:
                # 포트로 찾은 경우 .port까지 붙여서 표시
                display_name = f"{name}.{port}"
            else:
                display_name = name

            self.results_table.setItem(row_idx, 0, QTableWidgetItem(display_name))

        self.results_table.resizeColumnsToContents()
        # 긴 hierarchy를 위해 컬럼 너비를 강제로 넓게 설정 (horizontal scroll 유도)
        current_width = self.results_table.columnWidth(0)
        self.results_table.setColumnWidth(0, max(current_width, 1400))

        # 검색 결과 총 개수 표시 (라벨에)
        count = len(results)
        self.results_label.setText(f"Search Results ({count})")

    # ==================== Tree Highlighting (B) ====================

    def _highlight_tree_matches(self, results: List[Dict]):
        """Expand and select nodes that appear in the query results."""
        model = self.tree_view.model()
        if not model:
            return

        result_names = {r.get("name") or r.get("hierarchy", "") for r in results if r.get("name") or r.get("hierarchy")}

        # Simple approach: expand all and try to select first match
        self.tree_view.expandAll()

        first_match = None
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            self._find_and_select_match(model, index, result_names, first_match)

        if first_match:
            self.tree_view.scrollTo(first_match)
            self.tree_view.setCurrentIndex(first_match)

    def _find_and_select_match(self, model, index, result_names, first_match_ref):
        """Recursive helper to find and expand matching nodes."""
        item = model.itemFromIndex(index)
        if not item:
            return

        full_path = item.data(Qt.UserRole + 1)
        if full_path in result_names:
            self.tree_view.expand(index.parent() if index.parent().isValid() else index)
            if first_match_ref is None:
                first_match_ref = index  # type: ignore

        for r in range(item.rowCount()):
            child_index = model.index(r, 0, index)
            self._find_and_select_match(model, child_index, result_names, first_match_ref)

    # ==================== Result Selection → Source Viewer (D) ====================

    def _on_results_table_selected(self):
        """Full Hierarchy 테이블에서 행 선택 시 소스 뷰어 업데이트"""
        selected = self.results_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        if not hasattr(self, 'results_data') or row >= len(self.results_data):
            return

        item = self.results_data[row]
        file_path = item.get("file", "")
        hierarchy = item.get("name") or item.get("hierarchy", "")

        self.source_path_label.setText(f"File: {file_path}")

    def _on_results_table_double_clicked(self, index):
        """Full Hierarchy 더블클릭 → 트리에서 해당 인스턴스 찾기 + 노랑 굵게 강조 + 소스 열기"""
        row = index.row()
        if not hasattr(self, 'results_data') or row >= len(self.results_data):
            return

        item = self.results_data[row]
        hierarchy = item.get("name") or item.get("hierarchy", "")

        # 1. 트리에서 해당 노드 찾아 강조 + 이동
        self._find_and_highlight_in_tree(hierarchy)

        # 2. 소스 열기 (이 함수가 내부적으로 file_path 처리 및 포트/인스턴스 강조까지 담당)
        self._try_open_source_for_instance(item)

    def _resolve_source_file(self, file_path: str) -> Optional[Path]:
        """Try multiple locations to find the source file.
        Priority:
        1. Absolute
        2. User-set source_root
        3. Currently loaded filelist's base directory (very useful!)
        4. Project root
        """
        p = Path(file_path)

        candidates = []

        # 1. Absolute path
        if p.is_absolute():
            candidates.append(p)

        # 2. User-specified RTL root (highest priority if set)
        if self.source_root:
            candidates.append(self.source_root / file_path)

        # 3. Currently loaded filelist's base directory (this is the key fix)
        if self.current_filelist and hasattr(self.current_filelist, 'base_dir'):
            candidates.append(self.current_filelist.base_dir / file_path)

        # 4. Project root as last resort
        candidates.append(PROJECT_ROOT / file_path)

        for cand in candidates:
            if cand.exists():
                return cand

        return None

    def _format_instance_info(self, item: Dict) -> str:
        """Return nice metadata when source file is missing."""
        name = item.get("name") or item.get("hierarchy", "")
        module = item.get("module", "")
        file_path = item.get("file", "")
        ports = item.get("ports", [])

        lines = [
            f"Hierarchy : {name}",
            f"Module    : {module}",
            f"File      : {file_path}",
            f"Ports     : {', '.join(ports) if isinstance(ports, list) else ports}",
        ]
        return "\n".join(lines)

    def _try_open_source_for_instance(self, item: dict):
        """인스턴스 데이터로부터 소스 파일을 자동으로 찾아 열어줌 (더블클릭 지원)"""
        file_path = item.get("file", "")
        hierarchy = item.get("name") or item.get("hierarchy", "")

        if not file_path:
            self.source_viewer.setPlainText(f"Hierarchy: {hierarchy}\n\n(No file information)")
            return

        resolved = self._resolve_source_file(file_path)

        self.source_path_label.setText(f"File: {file_path}")

        if resolved and resolved.exists():
            try:
                content = resolved.read_text(encoding="utf-8", errors="replace")
                self.source_viewer.setPlainText(content)
                self.source_viewer.moveCursor(QTextCursor.Start)
                self.source_path_label.setText(f"File: {resolved}")

                # 더 이상 자동으로 전체를 빨갛게 강조하지 않음.
                # 사용자가 소스뷰어 안에서 Find 기능으로 직접 검색해서 강조하도록 유도.
                # (필요하면 아래 주석 해제)
                # matched_port = item.get("_port", "")
                # if matched_port:
                #     self._highlight_text_in_source(matched_port)

            except Exception as e:
                self.source_viewer.setPlainText(f"[Error reading file]\n{resolved}\n\n{str(e)}")
        else:
            # 자동으로 못 찾으면 안내
            msg = self._format_instance_info(item)
            msg += f"\n\n[Source file not found automatically]\nPath: {file_path}"
            msg += "\n\nTip: Filelist을 열면 자동으로 해당 폴더를 기준으로 찾아줍니다."
            self.source_viewer.setPlainText(msg)

    def _highlight_text_in_source(self, text_to_find: str, color: QColor = QColor(200, 0, 0)):
        """소스 뷰어에서 특정 문자열을 글자색으로만 강조 (배경색 없이)"""
        if not text_to_find:
            return

        doc = self.source_viewer.document()
        cursor = QTextCursor(doc)

        fmt = QTextCharFormat()
        fmt.setForeground(color)
        fmt.setFontWeight(QFont.Bold)

        found_any = False
        while True:
            cursor = doc.find(text_to_find, cursor)
            if cursor.isNull():
                break
            found_any = True
            cursor.mergeCharFormat(fmt)

        if found_any:
            # 첫 번째 매칭 위치로 스크롤
            cursor = QTextCursor(doc)
            cursor = doc.find(text_to_find, cursor)
            if not cursor.isNull():
                self.source_viewer.setTextCursor(cursor)
                self.source_viewer.ensureCursorVisible()

    def _highlight_port_in_source(self, port_name: str, content: str = None):
        """포트 이름만 빨간 글자색으로 강조 (전체 라인이나 배경색 없이)"""
        if not port_name:
            return
        self._highlight_text_in_source(port_name, QColor(200, 0, 0))

    def _find_and_highlight_in_tree(self, full_name: str):
        """주어진 hierarchy 이름으로 트리를 찾아 노랑 굵게 강조 + 이동"""
        model = self.tree_view.model()
        if not model or not full_name:
            return

        def search(index):
            item = model.itemFromIndex(index)
            if item:
                if item.data(Qt.UserRole + 1) == full_name:
                    self._highlight_tree_item(item)
                    return True
            for r in range(model.rowCount(index)):
                child = model.index(r, 0, index)
                if search(child):
                    return True
            return False

        # 루트부터 검색
        for r in range(model.rowCount()):
            root_idx = model.index(r, 0)
            if search(root_idx):
                break

    def _select_tree_node_by_name(self, full_name: str):
        model = self.tree_view.model()
        if not model or not full_name:
            return

        # Simple recursive search
        def search(index: QModelIndex) -> Optional[QModelIndex]:
            item = model.itemFromIndex(index)
            if item and item.data(Qt.UserRole + 1) == full_name:
                return index
            for r in range(item.rowCount() if item else 0):
                found = search(model.index(r, 0, index))
                if found:
                    return found
            return None

        root = model.index(0, 0) if model.rowCount() > 0 else QModelIndex()
        # Search from invisible root children
        for r in range(model.rowCount()):
            idx = model.index(r, 0)
            found = search(idx)
            if found:
                self.tree_view.setCurrentIndex(found)
                self.tree_view.scrollTo(found)
                return

    # ==================== Tree Selection (bonus) ====================

    def _on_tree_selection_changed(self, selected, deselected):
        # Optional: future enhancement - filter results when tree node selected
        pass

    def _highlight_tree_item(self, item: QStandardItem):
        """트리 아이템을 굵은 노랑 배경으로 강조 (이전 강조는 해제)"""
        # 이전 강조 해제
        if self._highlighted_tree_item and self._highlighted_tree_item is not item:
            self._highlighted_tree_item.setBackground(Qt.NoBrush)
            self._highlighted_tree_item.setFont(QFont())

        # 새 아이템 강조
        from PySide6.QtGui import QBrush, QColor
        item.setBackground(QBrush(QColor("yellow")))
        font = item.font()
        font.setBold(True)
        item.setFont(font)

        self._highlighted_tree_item = item

        # 트리에서 해당 아이템으로 이동
        index = self.tree_view.model().indexFromItem(item)
        if index.isValid():
            self.tree_view.scrollTo(index)
            self.tree_view.setCurrentIndex(index)

    def _on_tree_double_clicked(self, index: QModelIndex):
        """트리에서 더블클릭 → 해당 노드로 이동 + 노랑 굵게 강조 + 소스 열기"""
        item = self.tree_view.model().itemFromIndex(index)
        if not item:
            return

        self._highlight_tree_item(item)

        inst_data = item.data(Qt.UserRole + 2)
        if inst_data:
            self._try_open_source_for_instance(inst_data)
        else:
            full_path = item.data(Qt.UserRole + 1)
            if full_path:
                for inst in self.current_data:
                    if inst.get("name") == full_path or inst.get("hierarchy") == full_path:
                        self._try_open_source_for_instance(inst)
                        break

    # ==================== Query File Loading (F) ====================

    def load_query_file(self):
        start_dir = self.last_query_dir or str(PROJECT_ROOT / "examples" / "queries")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Query Text File",
            start_dir,
            "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

            if not lines:
                QMessageBox.information(self, "Empty File", "No queries found in the file.")
                return

            # Load first query into input and run it
            self.query_input.setText(lines[0])
            self.run_query()

            # Add rest to history
            for q in lines[1:]:
                if q not in self.query_history:
                    self.query_history.append(q)

            self._refresh_history_combo()
            self.last_query_dir = str(Path(file_path).parent)
            self.status_bar.showMessage(f"Loaded {len(lines)} queries from {Path(file_path).name}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load query file:\n{e}")

    # ==================== Filelist Loading (분석 대상 filelist) ====================

    def open_filelist(self):
        if EDAFilelistParser is None:
            QMessageBox.critical(self, "Module Error", "EDAFilelistParser를 import할 수 없습니다.\ntools/eda_filelist_parser.py 확인 필요.")
            return

        start_dir = self.last_filelist_dir or str(PROJECT_ROOT / "demo_data")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Analysis Target Filelist",
            start_dir,
            "Filelist Files (*.f *.f);;All Files (*)"
        )
        if not file_path:
            return

        # UI를 진행 중 상태로 전환 (멈춘 것처럼 보이지 않게)
        self.filelist_list.hide()
        self.source_viewer.hide()
        self.elab_progress.show()
        self.elab_log.show()
        self.elab_progress.setValue(0)
        self.elab_log.clear()
        self.elab_log.append(f"Opening filelist: {Path(file_path).name}")

        self.open_filelist_btn.setEnabled(False)

        # 백그라운드 파싱
        self.filelist_thread = QThread()
        self.filelist_worker = FilelistParseWorker(file_path)
        self.filelist_worker.moveToThread(self.filelist_thread)

        self.filelist_thread.started.connect(self.filelist_worker.run)
        self.filelist_worker.progress.connect(self._on_filelist_progress)
        self.filelist_worker.finished.connect(self._on_filelist_finished)

        self.filelist_thread.start()

    def start_elaboration(self):
        if not self.current_filelist:
            return

        # UI 준비 (진행 중 표시)
        self.elaborate_btn.setEnabled(False)
        self.filelist_list.hide()
        self.source_viewer.hide()

        self.elab_progress.show()
        self.elab_log.show()
        self.elab_progress.setValue(0)
        self.elab_log.clear()
        self.elab_log.append("Starting elaboration from filelist...")

        # Thread + Worker 생성
        self.elab_thread = QThread()
        self.elab_worker = ElaborationWorker(self.current_filelist)
        self.elab_worker.moveToThread(self.elab_thread)

        # Signal 연결
        self.elab_thread.started.connect(self.elab_worker.run)
        self.elab_worker.progress.connect(self._on_elab_progress)
        self.elab_worker.finished.connect(self._on_elab_finished)

        self.elab_thread.start()

    def _on_elab_progress(self, percent: int, message: str):
        self.elab_progress.setValue(percent)
        self.elab_log.append(f"[{percent:3d}%] {message}")
        # 자동 스크롤
        self.elab_log.verticalScrollBar().setValue(self.elab_log.verticalScrollBar().maximum())

    def _on_elab_finished(self, success: bool, message: str, hierarchy_data: list):
        self.elab_thread.quit()
        self.elab_thread.wait()

        self.elab_progress.hide()
        self.elab_log.hide()

        if success:
            self.current_data = hierarchy_data
            self._rebuild_tree()
            self.source_viewer.show()
            self.source_viewer.setPlainText(
                f"Elaboration finished successfully.\n{message}\n\n"
                "Hierarchy tree has been updated. You can now run DQL queries."
            )
            self.status_bar.showMessage(f"Elaboration done: {message}")
            self.elaborate_btn.setEnabled(False)  # 이미 끝났으므로 비활성화

            # Elaboration 후 새 데이터 로드 → 검색 결과 라벨 초기화
            self.results_label.setText("Search Results (0)")
        else:
            self.source_viewer.show()
            self.source_viewer.setPlainText(f"Elaboration failed:\n{message}")
            self.status_bar.showMessage("Elaboration failed.")
            self.elaborate_btn.setEnabled(True)  # 다시 시도 가능하게

        # 파일 목록 다시 보여주기 (필요 시)
        if self.current_filelist:
            self.filelist_list.show()

    def _on_filelist_progress(self, percent: int, message: str):
        self.elab_progress.setValue(percent)
        self.elab_log.append(f"[{percent:3d}%] {message}")
        self.elab_log.verticalScrollBar().setValue(self.elab_log.verticalScrollBar().maximum())

    def _on_filelist_finished(self, parser):
        self.filelist_thread.quit()
        self.filelist_thread.wait()

        self.elab_progress.hide()
        self.elab_log.hide()
        self.source_viewer.show()
        self.open_filelist_btn.setEnabled(True)

        if parser is None:
            self.source_viewer.setPlainText("Filelist parsing failed.")
            return

        self.current_filelist = parser
        source_count = len(parser.get_source_files())
        incdir_count = len(parser.get_incdirs())

        self.status_bar.showMessage(
            f"Filelist loaded: {Path(parser.top_filelist).name}  |  Sources: {source_count}  |  +incdir: {incdir_count}"
        )

        self.elaborate_btn.setEnabled(True)
        self.last_filelist_dir = str(Path(parser.top_filelist).parent)

        if self.source_root is None:
            self.source_root = parser.base_dir

        self._show_filelist_preview(parser, str(parser.top_filelist))

    # ==================== Source Viewer Find (Vim 스타일) ====================

    def _on_find_text_changed(self, text: str):
        """검색어가 바뀌면 해당 글자만 빨간색으로 강조 (배경색 없이)"""
        self._clear_source_highlights()

        if not text:
            self._find_matches = []
            self._current_find_index = -1
            return

        doc = self.source_viewer.document()
        cursor = QTextCursor(doc)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(220, 0, 0))  # 선명한 빨강
        fmt.setFontWeight(QFont.Bold)

        self._find_matches = []
        while True:
            cursor = doc.find(text, cursor)
            if cursor.isNull():
                break
            cursor.mergeCharFormat(fmt)
            self._find_matches.append(cursor.position())

        if self._find_matches:
            self._current_find_index = 0
            self._jump_to_find_match(0)

    def _source_find_next(self, forward: bool = True):
        if not self._find_matches:
            return

        if forward:
            self._current_find_index = (self._current_find_index + 1) % len(self._find_matches)
        else:
            self._current_find_index = (self._current_find_index - 1) % len(self._find_matches)

        self._jump_to_find_match(self._current_find_index)

    def _jump_to_find_match(self, index: int):
        if not self._find_matches or index < 0 or index >= len(self._find_matches):
            return

        pos = self._find_matches[index]
        cursor = self.source_viewer.textCursor()
        cursor.setPosition(pos - len(self.find_edit.text()), QTextCursor.MoveAnchor)
        cursor.setPosition(pos, QTextCursor.KeepAnchor)
        self.source_viewer.setTextCursor(cursor)
        self.source_viewer.ensureCursorVisible()

    def _clear_source_highlights(self):
        """소스 뷰어의 모든 커스텀 포맷 제거 (기본 흰색으로 복원)"""
        cursor = self.source_viewer.textCursor()
        cursor.select(QTextCursor.Document)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#ffffff"))  # 기본 흰색
        fmt.setFontWeight(QFont.Normal)

        cursor.mergeCharFormat(fmt)
        cursor.clearSelection()
        self.source_viewer.setTextCursor(cursor)

    # ==================== Markdown Export ====================

    def export_results_to_md(self):
        if not self.last_results:
            QMessageBox.information(self, "No Results", "There are no search results to export.")
            return

        # Ensure .temp directory exists
        temp_dir = PROJECT_ROOT / ".temp"
        temp_dir.mkdir(exist_ok=True)

        from datetime import datetime
        now = datetime.now()
        default_name = f"rtl_dql_{now.strftime('%Y%m%d_%H%M%S')}.md"
        default_path = temp_dir / default_name

        # Generate markdown content
        md_lines = []

        # Header
        filelist_name = "N/A"
        if self.current_filelist:
            filelist_name = getattr(self.current_filelist, 'top_filelist', 'N/A')

        md_lines.append(f"# RTL DQL Search Report")
        md_lines.append("")
        md_lines.append("## Info")
        md_lines.append(f"- **Target Filelist**: {filelist_name}")
        md_lines.append(f"- **Date**: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append(f"- **User**: {os.getenv('USER', 'unknown')}")
        md_lines.append("")

        # Query section
        current_query = self.query_input.text().strip() or "(no query)"
        md_lines.append("## Used Query")
        md_lines.append(f"```dql")
        md_lines.append(current_query)
        md_lines.append("```")
        md_lines.append("")

        # Results
        md_lines.append("## Found Hierarchies")
        md_lines.append("")

        for item in self.last_results:
            name = item.get("name") or item.get("hierarchy", "")
            filepath = item.get("file", "")
            md_lines.append(f"- `{name}`\t`{filepath}`")

        content = "\n".join(md_lines)

        # Save to default .temp location first
        try:
            with open(default_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.status_bar.showMessage(f"Report saved to {default_path}")
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save default report:\n{e}")
            return

        # Ask user if they want to export to custom location
        reply = QMessageBox.question(
            self,
            "Export Report",
            f"Default report saved to:\n{default_path}\n\nDo you want to save a copy to another location?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Markdown Report",
                str(default_path),
                "Markdown Files (*.md)"
            )
            if save_path:
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.status_bar.showMessage(f"Report exported to {save_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    def _show_filelist_preview(self, parser: "EDAFilelistParser", filelist_path: str):
        """Filelist 로드 시 오른쪽에 파일 목록을 보여주고 클릭하면 내용 표시."""
        self.filelist_list.clear()
        self.filelist_list.show()

        for src_file in parser.source_files:
            item = QListWidgetItem(str(src_file))
            item.setData(Qt.UserRole, src_file)  # store Path
            self.filelist_list.addItem(item)

        self.source_viewer.setPlainText(
            f"Filelist loaded: {filelist_path}\n"
            f"Total files: {len(parser.source_files)}\n\n"
            "Click a file in the list above to view its content.\n"
            "Click 'Elaborate' to extract hierarchy for DQL queries.")

        # 새 filelist 로드 시 검색 결과 라벨 초기화
        self.results_label.setText("Search Results (0)")
        self.source_path_label.setText(f"Filelist: {Path(filelist_path).name}  ({len(parser.source_files)} files)")

    def _on_filelist_file_clicked(self, item: QListWidgetItem):
        """파일 목록에서 파일 클릭 시 실제 내용 표시."""
        file_path: Path = item.data(Qt.UserRole)
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8", errors="replace")
                self.source_viewer.setPlainText(content)
                self.source_viewer.moveCursor(QTextCursor.Start)
                self.source_path_label.setText(str(file_path))
            else:
                self.source_viewer.setPlainText(f"[File not found]\n{file_path}")
        except Exception as e:
            self.source_viewer.setPlainText(f"[Error reading file]\n{file_path}\n\n{str(e)}")

    # ==================== History ====================

    def _refresh_history_combo(self):
        self.history_combo.clear()
        self.history_combo.addItems(self.query_history)

    def _on_history_selected(self, text: str):
        if text:
            self.query_input.setText(text)
            self.run_query()

    # ==================== Helpers ====================

    def _add_to_history(self, query: str):
        if query and query not in self.query_history:
            self.query_history.insert(0, query)
            if len(self.query_history) > 15:
                self.query_history = self.query_history[:15]
            self._refresh_history_combo()


def main():
    app = QApplication(sys.argv)

    # Dark theme + styling
    app.setStyle("Fusion")
    dark_style = """
    QMainWindow, QWidget { background-color: #1e1e2e; color: #ddd; }
    QLineEdit, QTextEdit, QTableWidget, QListWidget, QComboBox, QTreeView {
        background-color: #252535;
        color: #ddd;
        border: 1px solid #444;
        selection-background-color: #3a4a7a;
    }
    QPushButton {
        background-color: #3a3a4a;
        color: white;
        border: 1px solid #555;
        padding: 6px 14px;
        border-radius: 4px;
    }
    QPushButton:hover { background-color: #4a4a5a; }
    QPushButton:pressed { background-color: #2a2a3a; }
    /* Colored action buttons */
    QPushButton#btn_filelist { background-color: #2a5a2a; }
    QPushButton#btn_elaborate { background-color: #5a3a2a; }
    QPushButton#btn_query { background-color: #2a3a5a; }
    QPushButton#btn_export { background-color: #4a2a5a; }
    QHeaderView::section { background-color: #2f2f42; color: white; }
    QStatusBar { background-color: #16161f; color: #aaa; }
    QLabel { color: #ccc; }
    """
    app.setStyleSheet(dark_style)

    window = RtlDqlGui()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
