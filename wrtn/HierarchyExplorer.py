import sys
import json
import re
import Levenshtein  # Levenshtein 거리 계산을 위한 라이브러리
from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QLineEdit, QVBoxLayout, QWidget, QDesktopWidget, QMenu, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer

class HierarchyExplorer(QMainWindow):
    def __init__(self, hierarchy_data):
        super().__init__()
        self.hierarchy_data = hierarchy_data
        self.match_percentage = 90  # Default match percentage
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Hierarchy Explorer")

        # Set the size to 1/2 of the screen size
        screen = QDesktopWidget().screenGeometry()
        self.setGeometry(screen.x(), screen.y(), screen.width() // 2, screen.height() // 2)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Layout for main window
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.search_entry = QLineEdit(self)
        self.search_entry.setPlaceholderText("Enter search pattern or regex")
        self.layout.addWidget(self.search_entry)

        # Create the main tree widget
        self.tree = QTreeWidget(self)
        self.layout.addWidget(self.tree)

        # Create a layout for the result list
        self.result_layout = QVBoxLayout()
        self.result_label = QLabel("Matches (100% to):")
        self.result_layout.addWidget(self.result_label)

        # Create the percentage input
        self.percentage_input = QLineEdit(self)
        self.percentage_input.setPlaceholderText("Enter match percentage (default: 90%)")
        self.percentage_input.setFixedWidth(200)
        self.percentage_input.setText("90")  # Set default to 90
        self.result_layout.addWidget(self.percentage_input)

        # Create the results list widget
        self.results_list = QListWidget(self)
        self.results_list.setSelectionMode(QListWidget.MultiSelection)  # Enable multiple selection
        self.result_layout.addWidget(self.results_list)

        self.layout.addLayout(self.result_layout)

        # Create buttons for selection actions
        button_layout = QHBoxLayout()
        self.select_all_button = QPushButton("Select All")
        self.deselect_all_button = QPushButton("Deselect All")
        self.copy_selected_button = QPushButton("Copy Selected")

        # Set button styles to banana color
        self.select_all_button.setStyleSheet("background-color: #E3C65B;")  # Banana color
        self.deselect_all_button.setStyleSheet("background-color: #E3C65B;")  # Banana color
        self.copy_selected_button.setStyleSheet("background-color: #E3C65B;")  # Banana color

        button_layout.addWidget(self.select_all_button)
        button_layout.addWidget(self.deselect_all_button)
        button_layout.addWidget(self.copy_selected_button)

        self.layout.addLayout(button_layout)

        # Connect button actions
        self.select_all_button.clicked.connect(self.select_all)
        self.deselect_all_button.clicked.connect(self.deselect_all)
        self.copy_selected_button.clicked.connect(self.copy_selected_hierarchies)

        self.populate_tree()

        # Connect the textChanged signal to the search function
        self.search_entry.textChanged.connect(self.search)
        self.percentage_input.textChanged.connect(self.on_percentage_input)

        # Timer for processing percentage input
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.update_percentage)

        # Context menu for right-click
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

    def on_percentage_input(self):
        # Start the timer when the user types in the percentage input
        self.timer.start(2000)  # 2 seconds

    def update_percentage(self):
        # Update match percentage based on user input
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

    def populate_tree(self, parent_item=None, data=None):
        if data is None:
            data = self.hierarchy_data

        for key, value in data.items():
            item = QTreeWidgetItem([key])
            if parent_item:
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

            if isinstance(value, dict) and "instances" in value:
                self.populate_tree(item, value["instances"])

    def search(self):
        search_pattern = self.search_entry.text()
        # Clear previous highlights and results
        self.clear_highlights()
        self.results_list.clear()

        # Reset background color
        self.search_entry.setStyleSheet("")  # Reset background color

        if search_pattern:  # Only search if there is input
            try:
                # Check if the input is a valid regex
                try:
                    regex = re.compile(search_pattern)  # Compile the regex to check for validity
                except re.error:
                    self.search_entry.setStyleSheet("background-color: orange;")  # Invalid regex
                    return

                matches = self.tree.findItems("", Qt.MatchContains | Qt.MatchRecursive)  # Get all items

                # Filter items based on regex
                for item in matches:
                    full_hierarchy = self.get_full_hierarchy(item)
                    if regex.fullmatch(full_hierarchy):  # 100% match
                        self.results_list.addItem(QListWidgetItem(f"{full_hierarchy} (100%)"))  # Add to results
                    elif regex.search(full_hierarchy):  # Check match percentage
                        # Add to results only if it meets the match percentage
                        if self.match_percentage <= 90:  # 90% matches
                            self.results_list.addItem(QListWidgetItem(f"{full_hierarchy}"))  # Add to results
                        # Extend this to specify other percentage ranges if needed

                if self.results_list.count() == 0:
                    self.search_entry.setStyleSheet("background-color: orange;")  # Change background to orange
                else:
                    self.search_entry.setStyleSheet("background-color: yellow;")  # Change background to yellow

            except Exception as e:
                self.show_error_message(f"An error occurred during search: {str(e)}")

    def highlight_matching_text(self, full_hierarchy, search_pattern):
        list_item = QListWidgetItem(full_hierarchy)
        # Find the start index of the matching text
        start_index = full_hierarchy.lower().find(search_pattern.lower())
        if start_index != -1:
            # Create a new text with highlighted part
            highlighted_text = (
                    full_hierarchy[:start_index] +
                    "<font color='black' style='background-color: yellow;'>" +
                    full_hierarchy[start_index:start_index + len(search_pattern)] +
                    "</font>" +
                    full_hierarchy[start_index + len(search_pattern):]
            )
            list_item.setText(highlighted_text)
        else:
            list_item.setText(full_hierarchy)
        self.results_list.addItem(list_item)

    def get_full_hierarchy(self, item):
        # Get the full hierarchy from the item to the root
        hierarchy = []
        while item:
            hierarchy.append(item.text(0))
            item = item.parent()

        hierarchy.reverse()  # Reverse to get the correct order
        return '.'.join(hierarchy)  # Join with '.' to create the full hierarchy string

    def clear_highlights(self):
        # Reset all items in the tree to default background
        for index in range(self.tree.topLevelItemCount()):
            self.reset_item_background(self.tree.topLevelItem(index))

    def reset_item_background(self, item):
        if item:  # Ensure item is not None
            item.setBackground(0, Qt.white)  # Reset background to white
            for i in range(item.childCount()):
                self.reset_item_background(item.child(i))

    def expand_to_item(self, item):
        # Expand all parents of the item to make it visible
        while item:
            item.setExpanded(True)
            item = item.parent()

    def select_all(self):
        self.results_list.selectAll()  # Select all items in the results list

    def deselect_all(self):
        self.results_list.clearSelection()  # Deselect all items in the results list

    def copy_selected_hierarchies(self):
        selected_items = self.results_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select at least one hierarchy to copy.")
            return

        selected_hierarchies = [item.text().rsplit(' (', 1)[0] for item in selected_items]  # Exclude percentage
        hierarchy_str = '\n'.join(selected_hierarchies)  # Join selected hierarchies with newline
        QApplication.clipboard().setText(hierarchy_str)  # Copy to clipboard
        QMessageBox.information(self, "Copied", f"Copied hierarchies:\n{hierarchy_str}")

    def show_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item:
            menu = QMenu(self)
            copy_action = menu.addAction("Copy Selected Hierarchies")
            copy_action.triggered.connect(self.copy_selected_hierarchies)
            menu.exec_(self.tree.viewport().mapToGlobal(position))

    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)

def load_hierarchy_data(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def main(file_path):
    hierarchy_data = load_hierarchy_data(file_path)
    app = QApplication(sys.argv)
    explorer = HierarchyExplorer(hierarchy_data)
    explorer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hierarchy Explorer")
    parser.add_argument('-f', '--file', type=str, help='Path to the JSON file containing hierarchy data',
                        required=True)
    args = parser.parse_args()

    main(args.file)
