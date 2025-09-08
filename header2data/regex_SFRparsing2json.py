import os
import glob
import json
import argparse
import tempfile
import re
from pycparser import parse_file, c_ast
from pathlib import Path
import copy
from pyparsing import nestedExpr, Word, alphas, alphanums, Literal


class HeaderToJsonConverter:
    def __init__(self, input_dir, output_dir, db):
        """Initialize the converter with input and output directories."""
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.db = db if db else ''
        os.makedirs(output_dir, exist_ok=True)
        self.dTree = {}
        self.sm = 0
        self.temp = {}
        self.n = -1
        self.len = 0
        self.dKeys = {}
        self.surfix = {'pre': 'SFR_'}
        self.SFR = []
        self.fSfrHie = {}
        self.build()
        None

    def run(self, bitFields):
        self.SFR = bitFields
        self.genSFR()
        return self.fSfrHie

    def genSFR(self):
        for self.sfr in self.SFR:
            for fnm, v in self.dTree.items():
                if fnm not in self.fSfrHie:
                    self.fSfrHie[fnm] = {}
                self.sfrHie = []
                self.bitField = v['bitField']
                if self.sfr not in self.bitField:
                    break
                else:
                    if self.fullSFRPath(self.sfr, v):
                        if self.sfr not in self.fSfrHie[fnm]:
                            self.fSfrHie[fnm].update({self.sfr: []})
                        self.fSfrHie[fnm][self.sfr] += self.sfrHie 

    def fullSFRPath(self, sfr, d):
        self.dBitHie = [{i['upper']: i['c']} for i in d['bitField'][sfr]]
        for lb in self.dBitHie:
            for upper, self.bitFieldC in lb.items():
                self.sfrHie += [self.fullHieSFR(upper, d['struct'], top=d['top']) + '.' + self.bitFieldC]
        return self.sfrHie

    def fullHieSFR(self, upper, d, top=''):
        for i in d[upper]:
            if i['upper'] != top:
                _ = self.fullHieSFR(i['upper'], d, top=top)
                return _ + i['c'][i['c'].index('.'):]
            else:
                return i['c']

    def build(self):
        if not self.db:
            lh = self.find_h_files()
            for h in lh:
                self.fNM = os.path.basename(h)
                with open(h, "r", encoding="utf8") as f:
                    self.l = f.read()
                    self.l = re.sub(r"/\*.*?\*/", '', self.l, flags=re.DOTALL)
                    self.l = re.sub(r"//[^\n]+", '', self.l, flags=re.DOTALL)
                    self.make({})
                    # print(json.dumps(self.dTree, indent=4))
                    None
                self.dTree.update({self.fNM: {'bitField': self.dB, 'struct': self.dS, 'top': self.top}})
            with open(f"{self.output_dir}/rTree.json", "w", encoding="utf8") as f:
                f.write(json.dumps(self.dTree, indent=4))
        else:
            self.dTree = json.load(self.db)
            
    def make(self, d):
        self.union = re.findall(r"typedef volatile union _([\w]+) {([^,]+)[^;]+;", self.l, flags=re.MULTILINE|re.DOTALL)
        self.struct = re.findall(r"typedef volatile struct _([\w]+) {([^,]+)[^;]+;", self.l, flags=re.MULTILINE|re.DOTALL)
        self.dS = {}
        self.dB = {}
        self.getStructDB(self.struct)
        self.getBitFieldDB(self.union)
        self.top = self.findTop(self.dS)
        # print(json.dumps(self.dB, indent=4), json.dumps(self.dS, indent=4))

    def findTop(self, d):
        _ = list(set(sum([[i['upper'] for i in v] for k, v in d.items()], [])))
        _ = [i for i in _ if i not in d][0]
        return _

    def delSurfix(self, x):
        if x.startswith(self.surfix['pre']):
            return x[self.surfix['pre'].__len__():]
        return x

    def getBitFieldDB(self, x):
        if x:
            for (unm, u) in x:
                _b = re.findall(r"struct {([^}]+)} ([\w]+);", u, flags=re.MULTILINE|re.DOTALL)
                for st in _b:
                    mnm = self.delSurfix(st[1])
                    bits = st[0]
                    bits = [i.split(" :")[0].split(" ")[-1] for i in bits.lstrip().rstrip().split("\n")]
                    for bit in bits:
                        _bit = bit.strip('n').strip('an').split("[")[0]
                        if _bit not in self.dB:
                            self.dB[_bit] = []
                        self.dB[_bit] += [{'upper': self.delSurfix(unm), 'membernm': mnm, 'c': f'{mnm}.{bit.split("[")[0]}'}]
                    None
                None
            None

    def getStructDB(self, x):
        for st in x:
            unm = st[0]
            _s = [i.strip().rstrip(';') for i in st[1].split('}')[0].lstrip().rstrip().split("\n") if not any([i.strip().startswith(j) for j in ['uint', 'volatile ']])]
            _bits = "\n".join([i for i in st[1].split('}')[0].lstrip().rstrip().split("\n") if any([i.strip().startswith(j) for j in ['uint', 'volatile ']])])
            self.getBitFieldDB([[unm, f'struct {{\n' + _bits.replace(';', ' :') + f"\n}} {unm};"]] if _bits else False)
            for s in _s:
                if s:
                    _snm = s.split(" ")[0]
                    snm = self.delSurfix(_snm)
                    scast = s.split(" ")[1].strip("n").strip("an").strip("ast").split("[")[0]
                    _nofixunm = self.delSurfix(unm)
                    if snm not in self.dS:
                        self.dS[snm] = []
                    _assign = s.split(" ")[1].split("[")[0]
                    self.dS[snm] += [{'upper': _nofixunm, 'assign': _assign, 'c': f"{unm}.{_assign}"}]
            None
        None


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
    parser.add_argument(
        "--db",
        default="",
        help="JSON to load built DB"
    )

    args = parser.parse_args()

    # Initialize and run converter
    converter = HeaderToJsonConverter(args.input_dir, args.output_dir, args.db)
    result = converter.run(['W', 'TEST0', "WW"])
    print(json.dumps(result, indent=4))

if __name__ == "__main__":
    main()