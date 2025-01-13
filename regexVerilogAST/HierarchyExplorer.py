import sys
import json
import re
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QLabel, QHBoxLayout, QDesktopWidget, QMenu, QSplitter, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer
import argparse
import time
import copy


class HierarchyExplorer(QMainWindow):
    def __init__(self, hierarchy_data):
        super().__init__()
        self.hierarchy_data = hierarchy_data
        self.match_percentage = 90  # Default match percentage
        self.initUI()
        self.last_selected_index = None  # Track the last selected index for SHIFT selection

    def initUI(self):
        self.setWindowTitle("Hierarchy Explorer")
        screen = QDesktopWidget().screenGeometry()
        self.setGeometry(screen.x(), screen.y(), screen.width() // 2, screen.height() // 2)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()  # Use vertical layout for main widget
        self.central_widget.setLayout(self.layout)

        self.search_entry = QLineEdit(self)
        self.search_entry.setPlaceholderText("Enter search pattern or regex (* for any, ? for single character)")
        self.layout.addWidget(self.search_entry)

        # Create a splitter for left and right sections
        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)

        # Left side layout for tree and search results
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout()
        self.left_widget.setLayout(self.left_layout)

        self.tree = QTreeWidget(self)
        self.tree.itemDoubleClicked.connect(self.add_to_selected)  # Connect double click to add item
        self.left_layout.addWidget(self.tree)

        self.result_label = QLabel("Matches (100% to):")
        self.left_layout.addWidget(self.result_label)

        self.percentage_input = QLineEdit(self)
        self.percentage_input.setPlaceholderText("Enter match percentage (default: 90%)")
        self.percentage_input.setFixedWidth(200)
        self.percentage_input.setText("90")
        self.left_layout.addWidget(self.percentage_input)

        # Create a scroll area for the results list
        self.results_list = QListWidget(self)
        self.results_list.setSelectionMode(QListWidget.MultiSelection)
        self.results_list.setFixedHeight(200)  # Set a fixed height for scrolling
        self.results_list.itemDoubleClicked.connect(
            self.add_to_selected_from_results)  # Connect double click to add from results
        self.left_layout.addWidget(self.results_list)

        self.splitter.addWidget(self.left_widget)  # Add left widget to splitter

        # Right side layout for selected items with buttons
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout()
        self.right_widget.setLayout(self.right_layout)

        self.selected_list = QListWidget(self)
        self.selected_list.setSelectionMode(QListWidget.MultiSelection)  # Enable multi-selection
        self.selected_list.itemDoubleClicked.connect(self.remove_selected_from_list)  # Remove on double-click
        self.right_layout.addWidget(self.selected_list)

        button_layout = QHBoxLayout()
        self.remove_selected_button = QPushButton("Remove Selected")
        self.save_to_file_button = QPushButton("Save Selected to File")
        button_layout.addWidget(self.remove_selected_button)
        button_layout.addWidget(self.save_to_file_button)
        self.right_layout.addLayout(button_layout)

        self.splitter.addWidget(self.right_widget)  # Add right widget to splitter

        self.layout.addWidget(self.splitter)  # Add splitter to main layout

        # Connect button actions
        self.remove_selected_button.clicked.connect(self.remove_selected)
        self.save_to_file_button.clicked.connect(self.save_selected_to_file)  # Connect save button

        self.populate_tree()

        self.search_entry.textChanged.connect(self.search)
        self.percentage_input.textChanged.connect(self.on_percentage_input)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.update_percentage)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        # Right list context menu
        self.selected_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.selected_list.customContextMenuRequested.connect(self.show_right_context_menu)

    def populate_tree(self, parent_item=None, data=None):
        if data is None:
            data = self.hierarchy_data

        for key, value in data.items():
            item = QTreeWidgetItem([key])
            if parent_item:
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

            if isinstance(value, dict):
                # Add instances as children
                if "instances" in value:
                    self.populate_tree(item, value["instances"])

                # Add filepath at the end of the hierarchy string
                if "filepath" in value:
                    filepath = value["filepath"]
                    item.setText(0, f"{key} (filepath: {filepath})")  # Set the text to include filepath

    def search(self):
        search_pattern = self.search_entry.text()
        self.clear_highlights()
        self.results_list.clear()

        # Convert wildcard characters to regex
        search_pattern = search_pattern.replace('*', '.*').replace('?', '.')

        if search_pattern:
            try:
                regex = re.compile(search_pattern)
                matches = self.tree.findItems("", Qt.MatchContains | Qt.MatchRecursive)

                for item in matches:
                    full_hierarchy = self.get_full_hierarchy(item)
                    if regex.fullmatch(full_hierarchy):
                        self.results_list.addItem(QListWidgetItem(f"{full_hierarchy} (100%)"))
                    elif regex.search(full_hierarchy):
                        if self.match_percentage <= 90:
                            self.results_list.addItem(QListWidgetItem(f"{full_hierarchy}"))

                if self.results_list.count() == 0:
                    self.search_entry.setStyleSheet("background-color: orange;")
                else:
                    self.search_entry.setStyleSheet("background-color: yellow;")

            except Exception as e:
                self.show_error_message(f"An error occurred during search: {str(e)}")

    def get_full_hierarchy(self, item):
        hierarchy = []
        while item:
            hierarchy.append(item.text(0))
            item = item.parent()

        hierarchy.reverse()
        return '.'.join(hierarchy)

    def add_to_selected(self, item):
        # Add the double-clicked item to the selected list
        if item:
            full_hierarchy = self.get_full_hierarchy(item)
            if not self.selected_list.findItems(full_hierarchy, Qt.MatchExactly):
                self.selected_list.addItem(full_hierarchy)  # Add to right list

    def add_to_selected_from_results(self, item):
        # Add the double-clicked item from the results list to the selected list
        if item:
            full_hierarchy = item.text()
            if not self.selected_list.findItems(full_hierarchy, Qt.MatchExactly):
                self.selected_list.addItem(full_hierarchy)  # Add to right list

    def remove_selected(self):
        # Remove selected items from the selected list
        selected_items = self.selected_list.selectedItems()
        for item in selected_items:
            self.selected_list.takeItem(self.selected_list.row(item))

    def remove_selected_from_list(self, item):
        # Remove the double-clicked item from the selected list
        self.remove_selected()

    def save_selected_to_file(self):
        # Save selected items to a file
        selected_items = self.selected_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select at least one item to save.")
            return

        # Get the filename from the user
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt);;All Files (*)",
                                                   options=options)
        if file_path:
            with open(file_path, 'w') as file:
                for item in selected_items:
                    file.write(f"{item.text()}\n")  # Write each selected item to the file
            QMessageBox.information(self, "Saved", "Selected items have been saved to the file.")

    def on_percentage_input(self):
        self.timer.start(2000)  # 2 seconds

    def update_percentage(self):
        try:
            percentage = self.percentage_input.text().strip()
            if percentage == "":
                self.match_percentage = 100  # Treat empty input as 100%
            else:
                percentage = int(percentage)
                if 0 <= percentage <= 100:
                    self.match_percentage = percentage
                else:
                    self.match_percentage = 90  # Reset to default if out of range
                    self.percentage_input.setText("90")
        except ValueError:
            self.match_percentage = 90  # Reset to default on invalid input
            self.percentage_input.setText("90")

        self.search()  # Re-run the search with updated percentage

    def clear_highlights(self):
        for index in range(self.tree.topLevelItemCount()):
            self.reset_item_background(self.tree.topLevelItem(index))

    def reset_item_background(self, item):
        if item:
            item.setBackground(0, Qt.white)  # 배경색을 흰색으로 설정
            for i in range(item.childCount()):
                self.reset_item_background(item.child(i))  # 자식 항목에 대해 재귀 호출

    def show_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item:
            menu = QMenu(self)
            copy_action = menu.addAction("Copy Selected Hierarchies")
            copy_action.triggered.connect(lambda: self.copy_selected_hierarchies(item))
            menu.exec_(self.tree.viewport().mapToGlobal(position))

    def copy_selected_hierarchies(self, item):
        # 선택한 계층 구조를 클립보드에 복사
        hierarchy = self.get_full_hierarchy(item)
        QApplication.clipboard().setText(hierarchy)
        QMessageBox.information(self, "Copied", f"Copied hierarchy: {hierarchy}")

    def show_right_context_menu(self, position):
        # 오른쪽 목록의 컨텍스트 메뉴를 표시
        menu = QMenu(self)
        copy_action = menu.addAction("Copy Selected")
        select_all_action = menu.addAction("Select All")
        deselect_all_action = menu.addAction("Deselect All")

        copy_action.triggered.connect(self.copy_selected_to_clipboard)
        select_all_action.triggered.connect(self.select_all_items)
        deselect_all_action.triggered.connect(self.deselect_all_items)

        menu.exec_(self.selected_list.viewport().mapToGlobal(position))

    def copy_selected_to_clipboard(self):
        # 선택된 항목을 클립보드에 복사
        selected_items = self.selected_list.selectedItems()
        if selected_items:
            copied_text = "\n".join(item.text() for item in selected_items)
            QApplication.clipboard().setText(copied_text)
            QMessageBox.information(self, "Copied", "Selected items copied to clipboard.")

    def select_all_items(self):
        # 모든 항목 선택
        self.selected_list.selectAll()

    def deselect_all_items(self):
        # 모든 항목 선택 해제
        self.selected_list.clearSelection()

    def no_gui_mode(self, patterns):
        output_dir = "outputs_foundedHie"
        os.makedirs(output_dir, exist_ok=True)  # Create the output directory if it doesn't exist

        results = {}
        total_tSearch_hierarchy = 0
        total_tBuild_hierarchy = 0
        start_time = time.time()

        # 트리 구조 생성
        tree_rootTop = build_hierarchy_tree(self.hierarchy_data)
        for k, tree_root in tree_rootTop.items():
            tree_time = time.time() - start_time

            # 찾고자 하는 정규 표현식 패턴
            pattern = patterns.replace(",", "|").replace("*", "\\w*")

            # 인스턴스 찾기
            pattern_start_time = time.time()
            found_instances = find_full_hierarchy(tree_root, pattern)

            tSearch_hierarchy = time.time() - pattern_start_time
            total_tSearch_hierarchy += tSearch_hierarchy

            # Store results in a dictionary
            results[k] = {
                "topMpdule": k,
                "pattern": pattern,
                "#matches": found_instances.__len__(),
                "matches": found_instances,
                "tBuild_hierarchy": tree_time,
                "tSearch_hierarchy": tSearch_hierarchy
            }

        # Save all results to a JSON file
        json_file_path = os.path.join(output_dir, 'result_foundedHie.json')
        with open(json_file_path, 'w') as json_file:
            json.dump(results, json_file, indent=4, ensure_ascii=False)  # Write JSON with indentation

        # Save total time to a separate file
        total_time_path = os.path.join(output_dir, 'total_time.txt')
        with open(total_time_path, 'w') as time_file:
            time_file.write(f"Total search time: {total_tSearch_hierarchy:.2f} seconds\n")
            time_file.write(f"Total hierarchy time: {total_tBuild_hierarchy:.2f} seconds\n")

        # Print results to the console
        for pattern, result in results.items():
            print(f"Pattern: {pattern}")
            print("Matches:")
            for match in result["matches"]:
                print(f"  - {match}")
            print(f"Hierarchy time: {result['tBuild_hierarchy']:.2f} seconds")
            print(f"Search time: {result['tSearch_hierarchy']:.2f} seconds")
            print(f"Saved to {json_file_path}")


def load_hierarchy_data(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def main(file_path, patterns):
    hierarchy_data = load_hierarchy_data(file_path)
    app = QApplication(sys.argv)
    explorer = HierarchyExplorer(hierarchy_data)

    if patterns:
        explorer.no_gui_mode(patterns)
    else:
        explorer.show()

    sys.exit(app.exec_())


class HierarchyNode:
    def __init__(self, name):
        self.name = name
        self.children = []
        self.filepath = ""
        self.fileload = ""
        self.instance_map = {}  # 인스턴스 이름을 키로 하는 해시맵

    def add_child(self, child_node):
        self.children.append(child_node)
        # 인스턴스 이름을 해시맵에 추가
        self.instance_map[child_node.name] = child_node


def build_hierarchy_tree(hierarchy_dict):
    """계층 구조를 트리로 변환하는 함수"""
    if not isinstance(hierarchy_dict, dict):
        return None

    rootTop = {}
    for i in list(hierarchy_dict):
        root = HierarchyNode(i)
        root.filepath = hierarchy_dict[i]["filepath"]

        def recurse_dict(current_dict, parent_node):
            for key, value in current_dict.items():
                child_node = HierarchyNode(key)
                child_node.filepath = value["filepath"]
                child_node.fileload = value["fileload"]
                parent_node.add_child(child_node)
                if "instances" in value and isinstance(value["instances"], dict):
                    recurse_dict(value["instances"], child_node)

        recurse_dict(hierarchy_dict, root)
        rootTop[i] = copy.deepcopy(root)
    return rootTop


def find_full_hierarchy(tree, pattern):
    """트리에서 정규 표현식 패턴에 맞는 인스턴스를 찾고, 전체 계층을 반환하는 함수"""
    found_hierarchies = {}

    def dfs(node, current_path):
        # 현재 노드의 이름을 포함한 경로
        current_path.append(node.name)

        # 패턴과 매칭되는 경우 현재 경로를 추가
        if re.match(pattern.lower(), node.name.lower()):
            hie = ".".join(current_path)
            found_hierarchies.update({hie: {"hierarchy": hie, "filepath": node.filepath, "fileload": node.fileload}})

        for child in node.children:
            dfs(child, current_path.copy())  # 현재 경로를 복사하여 자식 노드 탐색

        current_path.pop()  # 탐색이 끝난 후 현재 노드 경로 삭제

    dfs(tree, [])
    return found_hierarchies

# __name__ 처리 부분
_thispath_ = os.path.dirname(__file__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hierarchy Explorer")
    parser.add_argument('-f', '--file', type=str, help='Path to the JSON file containing hierarchy data',
                        default=f"{_thispath_}/workdir/elab/elaboration_None.json")
    parser.add_argument('-p', '--patterns', type=str, help='Comma-separated patterns to search for', default="")
    args = parser.parse_args()

    main(args.file, args.patterns if args.patterns else [])
