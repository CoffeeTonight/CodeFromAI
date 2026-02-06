import pandas as pd
import os
import shutil
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Any, Union

# ==========================================
# 1. SystemRDL Full Access Property Map
# ==========================================
ACCESS_MAP = {
    'RW':    {'sw': 'rw', 'hw': 'r'},
    'RO':    {'sw': 'r',  'hw': 'rw'},
    'WO':    {'sw': 'w',  'hw': 'r'},
    'W1C':   {'sw': 'rw', 'hw': 'r', 'onwrite': 'wclr'},
    'W0C':   {'sw': 'rw', 'hw': 'r', 'onwrite': 'wclr'},
    'W1S':   {'sw': 'rw', 'hw': 'r', 'onwrite': 'wset'},
    'W0S':   {'sw': 'rw', 'hw': 'r', 'onwrite': 'wset'},
    'W1T':   {'sw': 'rw', 'hw': 'r', 'onwrite': 'wotoggle'},
    'W0T':   {'sw': 'rw', 'hw': 'r', 'onwrite': 'wztoggle'},
    'RC':    {'sw': 'r',  'hw': 'rw', 'onread': 'rclr'},
    'RS':    {'sw': 'r',  'hw': 'rw', 'onread': 'rset'},
    'WC':    {'sw': 'w',  'hw': 'r', 'onwrite': 'wclr'},
    'WS':    {'sw': 'w',  'hw': 'r', 'onwrite': 'wset'},
    'WRC':   {'sw': 'rw', 'hw': 'rw', 'onread': 'rclr'},
    'WRS':   {'sw': 'rw', 'hw': 'rw', 'onread': 'rset'},
    'W1CRS': {'sw': 'rw', 'hw': 'rw', 'onwrite': 'wclr', 'onread': 'rset'},
    'W0SRC': {'sw': 'rw', 'hw': 'rw', 'onwrite': 'wset', 'onread': 'rclr'},
    'WO1':   {'sw': 'w',  'hw': 'r', 'swwe': 'true'}, # Write once
}

# ==========================================
# 2. Intermediate Data Models (자료구조화)
# ==========================================
@dataclass
class FieldModel:
    name: str
    bit_range: str
    access: str
    reset: str = "0x0"
    desc: str = ""

@dataclass
class RegisterModel:
    name: str
    offset: str
    fields: List[FieldModel] = field(default_factory=list)
    repeat_count: int = 1
    stride: str = "0x4"
    desc: str = ""

@dataclass
class SubgroupModel:
    name: str
    repeat_count: int = 1
    size: str = "0x0"
    registers: List[RegisterModel] = field(default_factory=list)

@dataclass
class GroupModel:
    name: str
    repeat_count: int = 1
    size: str = "0x0"
    subgroups: List[SubgroupModel] = field(default_factory=list)
    registers: List[RegisterModel] = field(default_factory=list)

@dataclass
class AddrMapModel:
    name: str
    base_addr: str
    groups: List[GroupModel] = field(default_factory=list)

# ==========================================
# 3. Core Converter Class
# ==========================================
class SFRToSystemRDL:
    def __init__(self, xlsx_path: str):
        self.xlsx_path = xlsx_path
        self.addr_maps: List[AddrMapModel] = []
        self.params: Dict[str, Any] = {}

    def _parse_hex(self, val: Any) -> str:
        if pd.isna(val) or str(val).strip() == '': return "0x0"
        s = str(val).strip().lower()
        if s.startswith(('h', "'h")): return "0x" + s.split('h')[-1]
        try: return hex(int(s, 0))
        except: return str(val)

    def _resolve_repeat(self, val: str) -> int:
        if not val or val == '' or val == '1': return 1
        s = str(val).strip()
        if '..' in s:
            start, end = map(int, s.split('..'))
            return end - start + 1
        if s in self.params:
            return self._resolve_repeat(self.params[s])
        try: return int(float(s))
        except: return 1

    def build_structure(self):
        xls = pd.ExcelFile(self.xlsx_path)
        # 모든 memorymap 시트 탐색
        mm_sheets = [s for s in xls.sheet_names if "memorymap" in s]
        
        for mms in mm_sheets:
            mm_df = xls.parse(mms).fillna('')
            for _, row in mm_df.iterrows():
                if str(row['enable']).lower() not in ['yes', '1', 'true', 'y']: continue
                
                sheet_name = str(row['sheet']).strip()
                base_addr = int(self._parse_hex(row['base_addr']), 16) + int(self._parse_hex(row['addr_offset']), 16)
                inst_name = f"{row['module']}{row['naming_surfix']}"
                
                amap = AddrMapModel(name=inst_name, base_addr=hex(base_addr))
                if sheet_name in xls.sheet_names:
                    self._parse_sfr_sheet(xls, sheet_name, amap)
                    self.addr_maps.append(amap)

    def _parse_sfr_sheet(self, xls, sheet_name, amap):
        df_raw = xls.parse(sheet_name, header=None)
        
        # 1. Parameter 추출
        for _, row in df_raw.iterrows():
            line = [str(c).strip() for c in row if pd.notna(c)]
            if "Parameter" in line:
                idx = line.index("Parameter")
                self.params[line[idx+1]] = line[idx+2]

        # 2. 데이터 영역 추출
        header_idx = df_raw[df_raw.iloc[:, 0].astype(str).str.contains("Group Name", na=False)].index[0]
        data_df = pd.DataFrame(df_raw.iloc[header_idx+1:].values, columns=df_raw.iloc[header_idx].values)
        data_df = data_df.fillna('').applymap(lambda x: str(x).strip())

        cur_group, cur_subgroup, cur_reg = None, None, None

        for _, srow in data_df.iterrows():
            # Group Level
            gn = srow.get('Group Name')
            if gn:
                cur_group = GroupModel(name=gn, repeat_count=self._resolve_repeat(srow.get('Group Repeat Count')),
                                      size=self._parse_hex(srow.get('Group Size')))
                amap.groups.append(cur_group)
                cur_subgroup = None

            # Subgroup Level
            sgn = srow.get('Subgroup Name')
            if sgn and cur_group:
                cur_subgroup = SubgroupModel(name=sgn, repeat_count=self._resolve_repeat(srow.get('Subgroup Repeat Count')),
                                            size=self._parse_hex(srow.get('Subgroup Size')))
                cur_group.subgroups.append(cur_subgroup)

            # Register Level
            rn = srow.get('Register Name')
            if rn:
                cur_reg = RegisterModel(name=rn, offset=self._parse_hex(srow.get('Offset')), desc=srow.get('Description'))
                # Special Case: Bit Field에 반복 정보가 있는 경우 (stride, range)
                bf_val = srow.get('Bit Field', '')
                if ',' in bf_val and '0x' in bf_val:
                    stride, r_range = bf_val.split(',')
                    cur_reg.stride = self._parse_hex(stride)
                    cur_reg.repeat_count = self._resolve_repeat(r_range)
                
                if cur_subgroup: cur_subgroup.registers.append(cur_reg)
                elif cur_group: cur_group.registers.append(cur_reg)

            # Field Level
            fn = srow.get('Bit Field')
            if fn and not (',' in fn and '0x' in fn):
                f_obj = FieldModel(name=fn, bit_range=srow.get('Bit Range'),
                                  access=srow.get('Access Type', 'RW').upper(),
                                  reset=self._parse_hex(srow.get('Default Value')),
                                  desc=srow.get('Description'))
                if cur_reg: cur_reg.fields.append(f_obj)

    def generate_rdl(self) -> str:
        lines = ["/* Autogenerated Complex SystemRDL */\n"]
        for amap in self.addr_maps:
            lines.append(f"addrmap {amap.name}_map {{")
            for g in amap.groups:
                lines.append(f"  regfile {g.name}_gf {{")
                for sg in g.subgroups:
                    lines.append(f"    regfile {sg.name}_sgf {{")
                    for r in sg.registers: lines.append(self._render_reg(r, 3))
                    lines.append(f"    }} {sg.name}[{sg.repeat_count}] @= {sg.size};")
                for r in g.registers: lines.append(self._render_reg(r, 2))
                lines.append(f"  }} {g.name}[{g.repeat_count}] @= {g.size};")
            lines.append(f"}} {amap.name} @ {amap.base_addr};\n")
        return "\n".join(lines)

    def _render_reg(self, reg, indent):
        sp = "  " * indent
        res = [f"{sp}reg {reg.name}_t {{"]
        for f in reg.fields:
            p = ACCESS_MAP.get(f.access, {'sw':'rw'})
            p_str = " ".join([f"{k}={v};" for k, v in p.items()])
            res.append(f"{sp}  field {{ {p_str} reset={f.reset}; desc=\"{f.desc}\"; }} {f.name} {f.bit_range};")
        suffix = f"[{reg.repeat_count}] @= {reg.stride}" if reg.repeat_count > 1 else ""
        res.append(f"{sp}}} {reg.name}{suffix} @ {reg.offset};")
        return "\n".join(res)

# ==========================================
# 4. Main Execution & Test Handler
# ==========================================
def create_test_xlsx():
    test_xlsx = "test_spec.xlsx"
    with pd.ExcelWriter(test_xlsx, engine='openpyxl') as writer:
        # 공유해주신 memorymap 데이터
        mm_data = {
            'module': ['SystemCtrl', '', '', 'PeripheralCtrl', 'MainComplex', 'SubComplexA', 'SubComplexB', 'ExtraModule'],
            'base_addr': ['0x00000000', '0x10000', '0x20000', '0x30000000', '0x40000000', '0x50000000', '0x60000000', '0x80000000'],
            'addr_offset': ['0x0', '0x0', '0x0', '0x0', '0x0', '0x0', '0x0', '0x1000'],
            'enable': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'No'],
            'sheet': ['SystemCtrl', 'TimerGroup', 'IOGroup', 'PeripheralCtrl', 'ComplexSFR', 'ComplexSFR', 'ComplexSFR', 'ComplexSFR'],
            'addr_parameter': ['', 'NUM=0..1', '', '', '', 'NUM=0..3', '', ''],
            'naming_surfix': ['_ctrl', '_group', '_io', '_peri', '_main', '_sub_a', '_sub_b', '_extra']
        }
        pd.DataFrame(mm_data).to_excel(writer, sheet_name='memorymap', index=False)
        
        # ComplexSFR 데이터 (공유해주신 테이블 그대로)
        complex_sfr_data = [
            ['Parameter', 'NUM', '0..3'], ['Parameter', 'SFR_REPEAT', '0..2'],
            ['Group Name', 'Group Repeat Count', 'Group Size', 'Subgroup Name', 'Subgroup Repeat Count', 'Subgroup Size', 'Register Name', 'Offset', 'Bit Field', 'Bit Range', 'Default Value', 'Access Type', 'Testable', 'Description'],
            ['SystemCtrl', '1', '0x40', '', '', '', 'GlobalConfig', '0x00', 'Mode', '[1:0]', '0x0', 'RW', 'Y', 'System-wide mode control'],
            ['', '', '', '', '', '', '', '', 'Power', '[2:2]', '0x0', 'WO', 'N', 'Write-only power enable'],
            ['TimerGroup', '2', '0x80', 'Ctrl', '1', '0x20', 'TimerLoad', '0x40', 'LoadValue', '[31:0]', '0x0', 'RW', 'Y', 'Load timer'],
            ['PeripheralCtrl', '1', '0x100', '', '', '', 'singleRepeat', '0x300', '0x10,0..3', '[31:0]', '0x55', 'RW', 'Y', 'repeated sfr'],
            ['', '', '', '', '', '', 'longlong', '0x4AC', '', '[255:0]', '0', 'RW', 'Y', 'long long size sfr']
        ]
        pd.DataFrame(complex_sfr_data).to_excel(writer, sheet_name='ComplexSFR', index=False, header=False)
        
        # 다른 시트들도 생성 (동일 구조)
        pd.DataFrame(complex_sfr_data).to_excel(writer, sheet_name='SystemCtrl', index=False, header=False)
        pd.DataFrame(complex_sfr_data).to_excel(writer, sheet_name='TimerGroup', index=False, header=False)
        pd.DataFrame(complex_sfr_data).to_excel(writer, sheet_name='IOGroup', index=False, header=False)
        pd.DataFrame(complex_sfr_data).to_excel(writer, sheet_name='PeripheralCtrl', index=False, header=False)
    return test_xlsx

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str)
    parser.add_argument("--outdir", type=str, default="OUTPUT_xl2rdl")
    args = parser.parse_args()

    input_file = args.input if args.input else create_test_xlsx()
    
    base_dir = args.outdir
    rdl_dir = os.path.join(base_dir, "rdl")
    os.makedirs(rdl_dir, exist_ok=True)

    converter = SFRToSystemRDL(input_file)
    converter.build_structure()
    rdl_text = converter.generate_rdl()

    out_name = os.path.splitext(os.path.basename(input_file))[0] + ".rdl"
    with open(os.path.join(rdl_dir, out_name), "w", encoding='utf-8') as f:
        f.write(rdl_text)
    
    shutil.copy(input_file, os.path.join(base_dir, os.path.basename(input_file)))
    print(f"[*] Done. Output in: {base_dir}")

if __name__ == "__main__":
    main()
