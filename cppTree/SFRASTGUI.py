from PyQt6.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QPushButton
import sys

class SFRViewer(QMainWindow):
    def __init__(self, hierarchy):
        super().__init__()
        self.setWindowTitle("SFR Hierarchy Viewer")
        self.setGeometry(100, 100, 1000, 700)
        self.hierarchy = hierarchy

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Source", "SFR/Function", "Details"])
        layout.addWidget(self.tree)

        compare_btn = QPushButton("Compare & Merge")
        compare_btn.clicked.connect(self.compare_projects)
        layout.addWidget(compare_btn)

        self.load_projects()

    def load_projects(self):
        self.tree.clear()
        for source_id, project in self.hierarchy.projects.items():
            src_item = QTreeWidgetItem(self.tree, [source_id, "", f"Sources: {len(project.sources)}, Headers: {len(project.headers)}"])
            for sfr_name, sfr_node in project.sfrs.items():
                sfr_item = QTreeWidgetItem(src_item, ["", sfr_name, f"Address: {sfr_node.address or 'unknown'}"])
                for func, calls in sfr_node.called_by.items():
                    for loc, cond in calls:
                        QTreeWidgetItem(sfr_item, ["", func, f"{loc} [{cond or 'None'}]"])

    def compare_projects(self):
        print("Comparing projects...")

# 실행
hierarchy = SFRCallHierarchy()
project1 = hierarchy.add_project("developer1")
project1.parse_makefile("./cpp/Makefile", project1)  # 네 Makefile 경로 맞춰줘
project1.parse_files(project1)
app = QApplication(sys.argv)
window = SFRViewer(hierarchy)
window.show()
sys.exit(app.exec())