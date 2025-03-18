import tkinter as tk
from tkinter import ttk
import sys
from SFRCallHierarchy import SFRCallHierarchy


class SFRViewer:
    def __init__(self, hierarchy):
        self.root = tk.Tk()
        self.root.title("SFR Hierarchy Viewer")
        self.root.geometry("1000x700")
        self.hierarchy = hierarchy
        self.selected_sfrs = set()
        self.expanded_items = set()

        self.tree = ttk.Treeview(self.root, columns=("Source", "SFR/Function", "Details"), show="headings")
        self.tree.heading("Source", text="Source")
        self.tree.heading("SFR/Function", text="SFR/Function")
        self.tree.heading("Details", text="Details")
        self.tree.pack(fill="both", expand=True)

        compare_btn = tk.Button(self.root, text="Compare & Merge", command=self.compare_projects)
        compare_btn.pack()

        # 더블클릭 이벤트 바인딩
        self.tree.bind("<Double-1>", self.expand_ast)
        self.tree.tag_bind("sfr", "<Button-1>", self.toggle_selection)
        self.load_projects()

    def load_projects(self):
        self.tree.delete(*self.tree.get_children())
        for source_id, project in self.hierarchy.projects.items():
            parent = self.tree.insert("", "end", values=(
            source_id, "", f"Sources: {len(project.sources)}, Headers: {len(project.headers)}"))
            for sfr_name, sfr_node in project.sfrs.items():
                sfr_item = self.tree.insert(parent, "end",
                                            values=("", sfr_name, f"Address: {sfr_node.address or 'unknown'}"),
                                            tags=(sfr_name, "sfr"))
                for func, calls in sfr_node.called_by.items():
                    for loc, cond in calls:
                        self.tree.insert(sfr_item, "end", values=("", func, f"{loc} [{cond or 'None'}]"))
        if self.hierarchy.merged_project:
            parent = self.tree.insert("", "end", values=("Merged", "",
                                                         f"Sources: {len(self.hierarchy.merged_project.sources)}, Headers: {len(self.hierarchy.merged_project.headers)}"))
            for sfr_name, sfr_node in self.hierarchy.merged_project.sfrs.items():
                sfr_item = self.tree.insert(parent, "end",
                                            values=("", sfr_name, f"Address: {sfr_node.address or 'unknown'}"),
                                            tags=(sfr_name, "sfr"))
                for func, calls in sfr_node.called_by.items():
                    for loc, cond in calls:
                        self.tree.insert(sfr_item, "end", values=("", func, f"{loc} [{cond or 'None'}]"))

    def toggle_selection(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            tags = self.tree.item(item, "tags")
            print(f"Toggle clicked: item={item}, tags={tags}")  # 디버깅 출력
            if tags and "sfr" in tags:
                sfr_name = tags[0]
                if sfr_name in self.selected_sfrs:
                    self.selected_sfrs.remove(sfr_name)
                    self.tree.item(item, tags=(sfr_name, "sfr"))
                else:
                    self.selected_sfrs.add(sfr_name)
                    self.tree.item(item, tags=(sfr_name, "sfr", "selected"))
                self.tree.tag_configure("selected", background="yellow")

    def expand_ast(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            print("No item identified")  # 디버깅 출력
            return
        tags = self.tree.item(item, "tags")
        print(f"Double-clicked: item={item}, tags={tags}")  # 디버깅 출력
        if not tags or "sfr" not in tags:
            return

        sfr_name = tags[0]
        if item in self.expanded_items:
            self.tree.delete(*self.tree.get_children(item))
            self.expanded_items.remove(item)
            print(f"Collapsed {sfr_name}")
        else:
            self.expanded_items.add(item)
            for source_id, project in self.hierarchy.projects.items():
                if sfr_name in project.sfrs:
                    sfr_node = project.sfrs[sfr_name]
                    for func, calls in sfr_node.called_by.items():
                        func_item = self.tree.insert(item, "end", values=("", func, f"Called from {source_id}"))
                        for loc, cond in calls:
                            self.tree.insert(func_item, "end", values=("", "", f"Location: {loc} [{cond or 'None'}]"))
                            if func in project.functions:
                                for sub_func, sub_calls in project.functions[func].calls.items():
                                    self.tree.insert(func_item, "end", values=("", sub_func, f"Sub-call from {func}"))
            print(f"Expanded {sfr_name}")

    def compare_projects(self):
        comparison = self.hierarchy.compare_projects()
        self.hierarchy.merge_projects(self.selected_sfrs)
        self.load_projects()
        print("Comparison:", comparison)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SFR Call Hierarchy Frontend")
    parser.add_argument("--makefile", nargs='+', required=True, help="Path to one or more Makefiles")
    parser.add_argument("--output", default="report.json", help="Output JSON file")
    args = parser.parse_args()

    hierarchy = SFRCallHierarchy()
    for i, makefile in enumerate(args.makefile, 1):
        project = hierarchy.add_project(f"developer{i}")
        hierarchy.parse_makefile(makefile, project)
        hierarchy.parse_files(project)
    hierarchy.save_to_json(args.output)

    viewer = SFRViewer(hierarchy)
    viewer.run()