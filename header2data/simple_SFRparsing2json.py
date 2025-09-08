import os
import glob
import json
import argparse
import tempfile
import re
from pycparser import parse_file, c_ast
from pathlib import Path
import copy


class HeaderToJsonConverter:
    def __init__(self, input_dir, output_dir):
        """Initialize the converter with input and output directories."""
        self.input_dir = input_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.dTreeHtree = {}
        self.sm = 0
        self.temp = {}
        self.n = -1
        self.len = 0
        self.dKeys = {}
        self.run()

    def run(self):
        lh = self.find_h_files()
        for h in lh:
            self.fNM = os.path.basename(h)
            self.dTreeHtree[self.fNM] = {}
            self.dTreeTree = self.dTreeHtree[self.fNM]
            self.dTree = {}
            with open(h, "r", encoding="utf8") as f:
                self.l = f.read()
                self.l = re.sub(r"/\*.*?\*/", '', self.l, flags=re.DOTALL)
                self.l = re.sub(r"//[^\n]+", '', self.l, flags=re.DOTALL)
                self.l = self.l.split("\n")
                self.len = self.l.__len__() -1
                self.dTree = self.build({})
                print(json.dumps(self.dTree, indent=4))
                None
            
    def build(self, d):
        while self.n < self.len:
            self.n += 1
            _ = self.l[self.n].strip()
            if _.startswith("typedef volatile struct "):
                nm = _.rstrip().split(" ")[-2][1:]
                self.sm += 1
                d.update(self.build({}))
            elif _.startswith("typedef volatile union "):
                nm = _.rstrip().split(" ")[-2][1:]
                self.sm += 1
                d.update(self.build({}))
            elif _.startswith("struct {"):
                self.sm += 1
                d.update(self.build({}))
            elif self.sm == 2:
                if "volatile " in _:
                    _nm = _.split(" :")[0].rstrip().split(' ')[-1]
                    self.temp[_nm] = _.split(_nm)[0].lstrip().rstrip()
                elif "}" in _:
                    self.sm -= 1
                    nm = _.rstrip(';').split(",")[0][2:]
                    _d = {nm: copy.deepcopy(self.temp)}
                    self.temp = {}
                    return _d
            elif "}" in _:
                self.sm -= 1
                _nm = _.rstrip(';').split(",")[0][2:]
                return {_nm: d}
            elif self.sm == 1 and _.strip() != '':
                _n = _.split(';')[0].split(' :')[0].split('[')[0]
                _nm = _n.split(' ')[-1]
                if [i for i in ['volatile ', 'uint'] if i in _n]:
                    self.dKeys[_nm] = None
                else:
                    self.dKeys[_n.split(' ')[0]] = _nm
                d.update({_nm: _n.split(_nm)[0].lstrip().rstrip()})
        return d

    def find_h_files(self):
        folder = Path(self.input_dir)
        h_files = [str(file) for file in folder.rglob('*.h')]
        return h_files


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Convert C header files to JSON schemas.")
    parser.add_argument(
        "--input-dir",
        default="/home/user/workspace/CodeFromAI/header2data",
        help="Directory containing header files (default: /home/user/workspace/CodeFromAI/header2data)"
    )
    parser.add_argument(
        "--output-dir",
        default="OUTPUT",
        help="Directory to store JSON output files (default: OUTPUT)"
    )

    args = parser.parse_args()

    # Initialize and run converter
    converter = HeaderToJsonConverter(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()