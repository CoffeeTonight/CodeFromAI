import pandas as pd
import os
import re
import logging
import sys
import shutil
import argparse
from datetime import datetime
from tqdm import tqdm
from pathlib import Path
from typing import Any, Dict, List, Union
from dataclasses import dataclass, field

# Access Type Mapping
ACCESS_MAP = {
    'RW':   {'sw': 'rw', 'hw': 'rw'},
    'RO':   {'sw': 'r',  'hw': 'w'},
    'WO':   {'sw': 'w',  'hw': 'r'},
    'W1C':  {'sw': 'w',  'hw': 'r', 'onwrite': 'clr'},
    'RC':   {'sw': 'r',  'hw': 'w', 'onread': 'clr'},
    'W0C':  {'sw': 'w',  'hw': 'r', 'onwrite': 'clr'},
    'RS':   {'sw': 'r',  'hw': 'w', 'onread': 'set'},
    'WC':   {'sw': 'w',  'hw': 'r', 'onwrite': 'clr'},
    'WRC':  {'sw': 'rw', 'hw': 'rw', 'onread': 'clr'},
    'WS':   {'sw': 'w',  'hw': 'r', 'onwrite': 'set'},
    'W1T':  {'sw': 'w',  'hw': 'r', 'onwrite': 'onetoggle'},
    'W0T':  {'sw': 'w',  'hw': 'r', 'onwrite': 'zerotoggle'},
    'WO1':  {'sw': 'w',  'hw': 'r', 'onwrite': 'oneset'},
    'W1S':  {'sw': 'w',  'hw': 'r', 'onwrite': 'oneset'},
    'W0S':  {'sw': 'w',  'hw': 'r', 'onwrite': 'zeroset'},
    'WRS':  {'sw': 'rw', 'hw': 'rw', 'onread': 'set'},
    'W1CRS':{'sw': 'w', 'hw': 'r', 'onwrite': 'clr', 'onread': 'set'},
    'W0SRC':{'sw': 'w', 'hw': 'r', 'onwrite': 'clr', 'onread': 'set'},
}

def access_to_property(access: str) -> str:
    props = ACCESS_MAP.get(access.strip().upper(), {'sw': 'rw', 'hw': 'rw'})
    return ' '.join(f'{k} = {v};' for k, v in props.items())

def setup_logger(base_dir: str, excel_filename: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(base_dir) / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"{timestamp}_2RDL_{excel_filename}.log"
    
    logger = logging.getLogger("SFRToRDL")
    logger.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

@dataclass
class RdlContext:
    current_group: str = ""
    current_subgroup: str = ""
    current_reg: str = ""
    indent_level: int = 1  # addrmap { 아래부터 1

    def reset_group(self):
        self.current_group = ""
        self.current_subgroup = ""
        self.current_reg = ""

    def reset_subgroup(self):
        self.current_subgroup = ""
        self.current_reg = ""

    def reset_reg(self):
        self.current_reg = ""

    def __str__(self):
        return f"Group: '{self.current_group}' | Subgroup: '{self.current_subgroup}' | Reg: '{self.current_reg}' | Indent: {self.indent_level}"

class SFRToSystemRDL:
    def __init__(self, xlsx_path: str, output_dir: str = None):
        if xlsx_path is None:
            raise ValueError("xlsx_path cannot be None. Test file creation failed.")
        self.xlsx_path = Path(xlsx_path).resolve()
        self.excel_filename = self.xlsx_path.name
        
        self.base_dir = Path(output_dir) if output_dir else Path("OUTPUT_2RDL")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.systemrdl_dir = self.base_dir / "systemrdl"
        self.source_xlsx_dir = self.base_dir / "source_xlsx"
        self.systemrdl_dir.mkdir(exist_ok=True)
        self.source_xlsx_dir.mkdir(exist_ok=True)
        
        self.logger = setup_logger(self.base_dir, self.excel_filename)
        self.logger.info(f"Starting conversion for: {self.xlsx_path}")
        self.logger.info(f"Output directory: {self.base_dir}")
        
        dest_xlsx = self.source_xlsx_dir / self.excel_filename
        if not dest_xlsx.exists():
            shutil.copy2(self.xlsx_path, dest_xlsx)
            self.logger.info(f"Copied source XLSX to: {dest_xlsx}")
        else:
            self.logger.info(f"Source XLSX already exists at: {dest_xlsx}")
        
        self.xls = pd.ExcelFile(self.xlsx_path)
        self.memorymap_dfs = {}
        self.sfr_dfs = {}
        self.parameters = {}

    def parse_verilog_hex(self, value: Any) -> str:
        if not isinstance(value, str):
            return str(value)
        value = value.strip()
        if value.lower().startswith(("h", "'h")):
            value = '0x' + value.lstrip("h'H").lstrip("'h")
        return value

    def parse_parameters(self, df: pd.DataFrame) -> Dict[str, Any]:
        params = {}
        for i in range(len(df)):
            row = df.iloc[i]
            cells = [str(cell).strip() for cell in row if pd.notna(cell)]
            j = 0
            while j < len(cells) - 2:
                if cells[j] == "Parameter":
                    name = cells[j+1]
                    value = cells[j+2]
                    if '..' in value:
                        try:
                            start, end = map(int, value.split('..'))
                            params[name] = list(range(start, end + 1))
                        except:
                            self.logger.warning(f"Invalid range format: {value}")
                    else:
                        params[name] = value
                    j += 3
                else:
                    j += 1
            if str(row.iloc[0]).strip() and "Parameter" not in str(row.iloc[0]):
                break
        self.logger.debug(f"Parsed {len(params)} parameters")
        return params

    def replace_parameters(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        def replace_cell(cell):
            if not isinstance(cell, str):
                return cell
            for name, value in params.items():
                if isinstance(value, list):
                    continue
                cell = cell.replace(name, str(value))
            return cell
        
        df = df.map(replace_cell)
        self.logger.debug("Parameter replacement completed")
        return df

    def load_sheets(self):
        self.logger.info("Loading memorymap sheets...")
        mm_sheets = [s for s in self.xls.sheet_names if s.startswith("memorymap")]
        self.logger.info(f"Found {len(mm_sheets)} memorymap sheets: {mm_sheets}")

        for sheet in mm_sheets:
            df = self.xls.parse(sheet)
            df = df.dropna(how='all').reset_index(drop=True).fillna('')
            if 'module' in df.columns:
                df['module'] = df['module'].ffill()
            else:
                self.logger.warning(f"'module' column not found in {sheet} sheet")
            self.memorymap_dfs[sheet] = df

        sfr_sheet_names = set()
        for df in self.memorymap_dfs.values():
            if 'enable' in df.columns and 'sheet' in df.columns:
                enabled = df[df['enable'].astype(str).str.lower().isin(['1','true','y','yes'])]
                sfr_sheet_names.update(enabled['sheet'].dropna())

        for sheet_name in tqdm(sfr_sheet_names, desc="Loading SFR sheets"):
            if sheet_name not in self.xls.sheet_names:
                self.logger.warning(f"SFR sheet not found: {sheet_name}")
                continue
                
            df_full = self.xls.parse(sheet_name, header=None)
            self.parameters[sheet_name] = self.parse_parameters(df_full)
            
            header_idx = df_full[df_full.iloc[:, 0].str.contains("Group Name", na=False)].index
            if header_idx.empty:
                self.logger.error(f"No header row found in {sheet_name}")
                continue
            header_idx = header_idx[0]
            
            sfr_df = pd.DataFrame(
                df_full.iloc[header_idx+1:].values,
                columns=df_full.iloc[header_idx].values
            )
            sfr_df = sfr_df.dropna(how='all').reset_index(drop=True).fillna('')
            
            sfr_df.columns = [col.strip().replace(' ', '_').replace('-', '_') for col in sfr_df.columns]
            
            sfr_df = self.replace_parameters(sfr_df, self.parameters[sheet_name])
            
            hex_cols = ['Offset', 'Group_Size', 'Subgroup_Size']
            for col in hex_cols:
                if col in sfr_df.columns:
                    sfr_df[col] = sfr_df[col].apply(self.parse_verilog_hex)
            
            self.sfr_dfs[sheet_name] = sfr_df
            self.logger.info(f"Loaded SFR sheet '{sheet_name}' ({len(sfr_df)} rows)")

    def generate_top_memorymap(self) -> str:
        self.logger.info("Generating soc_top.rdl with shared bus support and dynamic naming")
        lines = ['addrmap soc_top {']
        
        bus_dict = {}
        prev_module = ""
        for mm_name, mm_df in self.memorymap_dfs.items():
            for _, row in tqdm(mm_df.iterrows(), total=len(mm_df), desc=f"{mm_name} rows"):
                if str(row['enable']).lower() not in ['1', 'true', 'y', 'yes']:
                    continue
                
                module = str(row['module']).strip() or prev_module
                prev_module = module
                sheet = str(row['sheet']).strip()
                base_addr = self.parse_verilog_hex(row['base_addr'] or '0x0')
                addr_offset = self.parse_verilog_hex(row['addr_offset'] or '0x0')
                surfix = str(row['naming_surfix'] or '').lstrip('_').strip()
                bus_if = row.get('bus_if', 'apb')
                bus_width = row.get('bus_data_width', '32')
                
                bus_version = re.match(r'(ahb|axi)(\d+)', bus_if.lower())
                if bus_version:
                    bus_type = bus_version.group(1)
                    version = bus_version.group(2)
                else:
                    bus_type = bus_if.lower()
                    version = ''
                
                bus_key = f"{bus_if}_{bus_width}"
                if bus_key not in bus_dict:
                    bus_dict[bus_key] = True
                    bus_name = f"{bus_type}_bus{version}_{bus_width}"
                    lines.append(f'  bus {bus_name} {{')
                    lines.append(f'    width = {bus_width};')
                    if 'axi4' in bus_if.lower():
                        lines.append('    qos_support = true;')
                    if 'axi3' in bus_if.lower():
                        lines.append('    locked_support = true;')
                    if 'ahb4' in bus_if.lower():
                        lines.append('    qos_support = true;')
                    if 'ahb3' in bus_if.lower():
                        lines.append('    locked_support = true;')
                    lines.append('  };')
                    lines.append(f'  {bus_name} {bus_type}_if{version}_{bus_width};')
                    lines.append('')
                
                try:
                    addr_int = int(base_addr, 0) + int(addr_offset, 0)
                    addr = hex(addr_int)
                except:
                    addr = '0x0'
                    self.logger.warning(f"Invalid address for {module}")
                
                instance_name = f"{module}_{surfix}_{bus_if}_{bus_width}" if surfix else f"{module}_{bus_if}_{bus_width}"
                
                if sheet.startswith('*'):
                    if '[' in sheet and ']' in sheet:
                        mem_type, depth_str = sheet[1:].split('[', 1)
                        depth = depth_str.rstrip(']')
                        depth = int(depth) if depth.isdigit() else depth
                        
                        if mem_type.upper() == 'SRAM':
                            sw = 'rw'
                        elif mem_type.upper() == 'ROM':
                            sw = 'ro'
                        else:
                            sw = 'rw'
                            self.logger.warning(f"Unknown memory type: {mem_type}")
                        
                        lines.append(f'  // Memory block: {module} ({mem_type}[{depth}])')
                        lines.append(f'  mem {instance_name} {{')
                        lines.append(f'    mementries = {depth};')
                        lines.append(f'    memwidth = {bus_width};')
                        lines.append(f'    sw = {sw};')
                        lines.append(f'  }} @ {addr};')
                        lines.append('')
                    else:
                        self.logger.warning(f"Invalid memory format in sheet: {sheet}")
                else:
                    lines.append(f'  // {module} - Bus: {bus_if}, Width: {bus_width}')
                    lines.append(f'  {sheet} {instance_name} @ {addr} using {bus_type}_if{version}_{bus_width};')
                    lines.append('')
        
        lines.append('};')
        self.logger.info(f"soc_top.rdl generated ({len(lines)} lines)")
        return '\n'.join(lines)

    def generate_sfr_addrmap(self, sheet_name: str, module_name: str, df: pd.DataFrame, bus_width: int = 32) -> str:
        self.logger.info(f"Generating RDL for {module_name} (sheet={sheet_name}, bus_width={bus_width}) ({len(df)} rows)")
        lines = [f'addrmap {module_name} {{']

        context = RdlContext()
        params = self.parameters.get(sheet_name, {})

        added_field = False

        for row_idx, row in enumerate(tqdm(df.itertuples(index=False), total=len(df), desc=f"Processing {sheet_name} ({module_name})")):
            row_dict = row._asdict()
            group = row_dict.get('Group_Name', '').strip()
            subgroup = row_dict.get('Subgroup_Name', '').strip()
            reg = row_dict.get('Register_Name', '').strip()
            offset = row_dict.get('Offset', '').strip()
            bit_field = row_dict.get('Bit_Field', '').strip()
            bit_range = row_dict.get('Bit_Range', '').strip()
            default = row_dict.get('Default_Value', '')
            access = row_dict.get('Access_Type', '')
            desc = row_dict.get('Description', '').replace('"', '\\"')

            group_repeat_str = row_dict.get('Group_Repeat_Count', '')
            group_size = row_dict.get('Group_Size', '0x0').strip()
            subgroup_repeat_str = row_dict.get('Subgroup_Repeat_Count', '')
            subgroup_size = row_dict.get('Subgroup_Size', '0x0').strip()
            group_repeat = len(params[group_repeat_str]) if group_repeat_str in params and isinstance(params[group_repeat_str], list) else int(group_repeat_str or 1)
            subgroup_repeat = len(params[subgroup_repeat_str]) if subgroup_repeat_str in params and isinstance(params[subgroup_repeat_str], list) else int(subgroup_repeat_str or 1)

            if not any([group, subgroup, reg, bit_field, offset]):
                continue

            # 그룹 변경
            if group and group != context.current_group:
                while context.indent_level > 1:
                    context.indent_level -= 1
                    lines.append('  ' * context.indent_level + '};')
                context.current_group = group
                context.reset_subgroup()
                stride = group_size
                indent = '  ' * context.indent_level
                lines.append(f'{indent}addrmap {{')
                context.indent_level += 1
                # ... 내부 내용 추가 후
                context.indent_level -= 1
                lines.append(f'{indent}}} {group}')
                if group_repeat > 1:
                    lines[-1] += f" {group}_inst[{group_repeat}]"
                if stride != '0x0':
                    lines[-1] += f" @ {stride}"
                lines[-1] += ';'

            # 서브그룹 변경
            if subgroup and subgroup != context.current_subgroup:
                while context.indent_level > 2:
                    context.indent_level -= 1
                    lines.append('  ' * context.indent_level + '};')
                context.current_subgroup = subgroup
                context.reset_reg()
                stride = subgroup_size
                indent = '  ' * context.indent_level
                lines.append(f'{indent}regfile {{')
                context.indent_level += 1
                # ... 내부 내용 추가 후
                context.indent_level -= 1
                lines.append(f'{indent}}} {subgroup}')
                if subgroup_repeat > 1:
                    lines[-1] += f" {subgroup}_inst[{subgroup_repeat}]"
                if stride != '0x0':
                    lines[-1] += f" @ {stride}"
                lines[-1] += ';'

            # 이전 레지스터 닫기
            if reg and reg != context.current_reg:
                if context.current_reg:
                    lines.append('  ' * context.indent_level + '};')
                    context.indent_level -= 1

                added_field = False

            is_repeat = bit_field and re.match(r'^0x[0-9a-fA-F]+ *,.*', bit_field)

            bit_width = 32
            if bit_range:
                try:
                    msb, lsb = map(int, re.findall(r'\[(\d+):(\d+)\]', bit_range)[0])
                    bit_width = msb - lsb + 1
                except Exception as e:
                    self.logger.warning(f"Row {row_idx}: Bit_Range 파싱 실패 '{bit_range}' - {e}")

            array_count = max(1, (bit_width + bus_width - 1) // bus_width)
            stride = hex(bus_width // 8) if bus_width > 0 else '0x4'

            if reg:
                context.current_reg = reg
                indent = '  ' * context.indent_level

                lines.append(f'{indent}reg {{')

                context.indent_level += 1

                if bit_width > 32:
                    lines.append(f'{"  " * context.indent_level}regwidth = {bit_width};')

                if bit_range and access and not added_field:
                    field_indent = '  ' * context.indent_level
                    field_name = bit_field if bit_field and bit_field.isidentifier() else 'data'
                    field_bit_range = f'[{bus_width-1}:0]' if array_count > 1 else bit_range
                    lines.append(f'{field_indent}field {{')
                    lines.append(f'{field_indent}  {access_to_property(access)}')
                    if default:
                        lines.append(f'{field_indent}  reset = {self.parse_verilog_hex(str(default))};')
                    if desc:
                        lines.append(f'{field_indent}  desc = "{desc}";')
                    lines.append(f'{field_indent}}} {field_name} {field_bit_range} = 0;')
                    added_field = True

                context.indent_level -= 1
                lines.append(f'{indent}}} {reg}')

                # 배열 인스턴스 (이름과 [N] 붙여씀, 공백 없음)
                if is_repeat:
                    size_str, repeat_str = [s.strip() for s in bit_field.split(',', 1)]
                    repeat = 1
                    if repeat_str in params and isinstance(params[repeat_str], list):
                        repeat = len(params[repeat_str])
                    elif '..' in repeat_str:
                        start, end = map(int, repeat_str.split('..'))
                        repeat = end - start + 1
                    else:
                        repeat = int(repeat_str or 1)
                    lines[-1] += f"{reg}_inst[{repeat}]"

                elif array_count > 1:
                    lines[-1] += f"{reg}_inst[{array_count}]"

                # 주소 지정 (같은 줄에 붙임)
                addr_suffix = ""
                if is_repeat and size_str and size_str != '0x
    def run(self):
        self.logger.info("=== Conversion Started ===")
        try:
            self.load_sheets()

            # module별 정보 매핑
            module_to_sheet = {}
            module_to_bw = {}
            prev_module = ""
            for mm_name, mm_df in self.memorymap_dfs.items():
                for _, row in tqdm(mm_df.iterrows(), total=len(mm_df), desc=f"Mapping {mm_name}"):
                    if str(row['enable']).lower() not in ['1', 'true', 'y', 'yes']:
                        continue
                    
                    module = str(row['module']).strip() or prev_module
                    prev_module = module
                    sheet = str(row['sheet']).strip()
                    bw = int(row.get('bus_data_width', 32))
                    
                    module_to_sheet[module] = sheet
                    module_to_bw[module] = bw

            # soc_top.rdl 생성
            top_rdl = self.generate_top_memorymap()
            top_path = self.systemrdl_dir / "soc_top.rdl"
            with open(top_path, 'w', encoding='utf-8') as f:
                f.write(top_rdl)
            self.logger.info(f"Saved top addrmap: {top_path}")

            # module별 RDL 생성
            for module, sheet_name in module_to_sheet.items():
                if sheet_name not in self.sfr_dfs:
                    self.logger.warning(f"SFR sheet not loaded for module {module} → skip")
                    continue
                
                df = self.sfr_dfs[sheet_name]
                bw = module_to_bw.get(module, 32)
                
                # sheet_name과 module_name 둘 다 전달
                rdl_content = self.generate_sfr_addrmap(sheet_name, module, df, bus_width=bw)
                path = self.systemrdl_dir / f"{module}.rdl"
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(rdl_content)
                self.logger.info(f"Saved RDL for module {module} (sheet={sheet_name}, bus_width={bw}): {path}")

            self.logger.info("=== Conversion Completed Successfully ===")
        except Exception as e:
            self.logger.error("Conversion failed", exc_info=True)
            raise

def create_test_xlsx():
    test_xlsx = "test_spec.xlsx"
    with pd.ExcelWriter(test_xlsx, engine='openpyxl') as writer:
        # memorymap
        mm_data = {
            'module': ['SystemCtrl', '', '', 'PeripheralCtrl', 'MainComplex', 'SubComplexA', 'SubComplexB', 'ExtraModule'],
            'base_addr': ['0x00000000', '0x10000', '0x20000', '0x30000000', '0x40000000', '0x50000000', '0x60000000', '0x80000000'],
            'addr_offset': ['0x0', '0x0', '0x0', '0x0', '0x0', '0x0', '0x0', '0x1000'],
            'enable': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'No'],
            'sheet': ['SystemCtrl', 'TimerGroup', 'IOGroup', 'PeripheralCtrl', 'ComplexSFR', 'ComplexSFR', 'ComplexSFR', 'ComplexSFR'],
            'addr_parameter': ['', 'NUM=0..1', '', '', '', 'NUM=0..3', '', ''],
            'sheet_parameter': ['', '', '', '', '', '', '', ''],
            'bus_if': ['apb', 'ahb', 'axi', 'apb', 'axi', 'axi', 'axi', 'apb'],
            'bus_data_width': [32, 64, 32, 32, 128, 128, 128, 32],
            'base_addr_check_off': ['', '', '', '', '', '', '', 'Y'],
            'naming_surfix': ['_ctrl', '_group', '_io', '_peri', '_main', '_sub_a', '_sub_b', '_extra'],
            'is_packet': ['No', 'No', 'No', 'No', 'No', 'No', 'No', 'No']
        }
        pd.DataFrame(mm_data).to_excel(writer, sheet_name='memorymap', index=False)
        
        # memorymap_a
        mm_a_data = {
            'module': ['PeriGroupA', 'PeriGroupB'],
            'base_addr': ['0xC0000000', '0xD0000000'],
            'addr_offset': ['0x0', '0x0'],
            'enable': ['Yes', 'Yes'],
            'sheet': ['ComplexSFR', 'ComplexSFR'],
            'addr_parameter': ['', 'NUM=0..2'],
            'sheet_parameter': ['', ''],
            'bus_if': ['apb', 'apb'],
            'bus_data_width': [32, 32],
            'base_addr_check_off': ['', ''],
            'naming_surfix': ['_peri_a', '_peri_b'],
            'is_packet': ['No', 'No']
        }
        pd.DataFrame(mm_a_data).to_excel(writer, sheet_name='memorymap_a', index=False)
        
        # ComplexSFR
        complex_sfr_data = [
            ['Parameter', 'NUM', '0..3'],
            ['Parameter', 'SFR_REPEAT', '0..2'], ['Parameter', 'BITW', '31'],
            ['Parameter', 'ADDR_OFFSET', 'h100'], ['Parameter', 'RESET_VAL', '0xA5'],
            ['Parameter', 'SIZE_64', '64'], ['Parameter', 'SIZE_128', '128'], ['Parameter', 'SIZE_256', '256'], ['Parameter', 'SIZE_512', '512'],
            ['Group Name', 'Group Repeat Count', 'Group Size', 'Subgroup Name', 'Subgroup Repeat Count', 'Subgroup Size', 'Register Name', 'Offset', 'Bit Field', 'Bit Range', 'Default Value', 'Access Type', 'Testable', 'Description'],
            ['SystemCtrl', '1', '0x40', '', '', '', 'GlobalConfig', '0x00', 'Mode', '[1:0]', '0x0', 'RW', 'Y', 'System-wide mode control'],
            ['', '', '', '', '', '', '', '', 'Power', '[2:2]', '0x0', 'WO', 'N', 'Write-only power enable'],
            ['', '', '', 'Ctrl', '1', '0x10', 'Control', '0x04', 'Enable', '[0:0]', '0x0', 'RW', 'Y', 'Enables clock source'],
            ['', '', '', '', '', '', '', '', 'Divider', '[7:1]', '0x1', 'RW', 'Y', 'Sets clock divider value'],
            ['', '', '', '', '', '', 'ClockStatus', '0x08', 'Locked', '[0:0]', '0x0', 'RO', 'Y', 'PLL lock status'],
            ['', '', '', '', '', '', '', '', 'Error', '[1:1]', '0x0', 'RC', 'Y', 'Read clears error flag'],
            ['', '', '', 'ResetCtrl', '1', '0x10', 'ResetReg', '0x14', 'SoftReset', '[0:0]', '0x0', 'WO', 'N', 'Write-only soft reset trigger'],
            ['', '', '', '', '', '', '', '', 'Watchdog', '[1:1]', '0x0', 'W1C', 'Y', 'Write 1 to clear watchdog'],
            ['', '', '', '', '', '', 'InterruptCtrl', '0x18', 'Mask', '[3:0]', '0xF', 'RW', 'Y', 'Interrupt mask bits'],
            ['', '', '', '', '', '', '', '', 'Pending', '[7:4]', '0x0', 'RO', 'Y', 'Pending interrupts (read-only)'],
            ['TimerGroup', '2', '0x80', 'Ctrl', '1', '0x20', 'TimerLoad', '0x40', 'LoadValue', '[31:0]', '0x0', 'RW', 'Y', 'Load timer counter value (1st instance)'],
            ['', '', '', '', '', '', 'Control', '0x44', 'Enable', '[0:0]', '0x0', 'RW', 'Y', 'Enable/disable timer'],
            ['', '', '', '', '', '', '', '', 'Mode', '[2:1]', '0x0', 'WO', 'N', 'Write-only mode selection'],
            ['', '', '', '', '', '', 'TimerStatus', '0x48', 'Overflow', '[0:0]', '0x0', 'W1T', 'Y', 'Write 1 to toggle overflow flag'],
            ['', '', '', '', '', '', '', '', 'Underflow', '[1:1]', '0x0', 'W0C', 'Y', 'Write 0 to clear underflow'],
            ['', '', '', 'TimerConfig', '1', '0x20', 'TimerLoad', '0xC0', 'LoadValue', '[31:0]', '0x0', 'RW', 'Y', 'Load timer counter value (2nd instance)'],
            ['', '', '', '', '', '', 'TimerControl', '0xC4', 'Enable', '[0:0]', '0x0', 'RW', 'Y', 'Enable/disable timer'],
            ['', '', '', 'InterruptSub', '1', '0x10', 'IntEnable', '0xE0', 'TimerInt', '[0:0]', '0x0', 'RW', 'Y', 'Enable timer interrupt (2nd instance)'],
            ['', '', '', '', '', '', 'IntStatus', '0xE4', 'Pending', '[0:0]', '0x0', 'RS', 'Y', 'Read sets status bit'],
            ['', '', '', '', '', '', '', '', 'Clear', '[1:1]', '0x0', 'WC', 'Y', 'Write clears all pending'],
            ['', '', '', '', '', '', 'MiscReg', '0xF0', 'Status', '[3:0]', '0x0', 'RO', 'Y', 'Standalone status register'],
            ['IOGroup', '1', '0x100', 'PortA', '4', '0x20', 'DataReg', '0x100', 'Output', '[7:0]', '0x00', 'RW', 'Y', 'Port data output (1st instance)'],
            ['', '', '', '', '', '', '', '', 'Input', '[15:8]', '0x00', 'RO', 'Y', 'Port data input (read-only)'],
            ['', '', '', '', '', '', 'DirReg', '0x104', 'Direction', '[7:0]', '0xFF', 'RW', 'Y', 'Set pin directions'],
            ['', '', '', '', '', '', 'InterruptReg', '0x108', 'Mask', '[3:0]', '0x0', 'WRC', 'Y', 'Write as-is, read clears'],
            ['', '', '', '', '', '', '', '', 'Trigger', '[7:4]', '0x0', 'WS', 'Y', 'Write sets bits'],
            ['', '', '', 'PortB', '', '', 'DataReg', '0x120', 'Output', '[7:0]', '0x00', 'RW', 'Y', 'Port data output (2nd instance)'],
            ['', '', '', 'PortC', '', '', 'DataReg', '0x140', 'Output', '[7:0]', '0x00', 'RW', 'Y', 'Port data output (3rd instance)'],
            ['', '', '', 'PortD', '', '', 'DataReg', '0x160', 'Output', '[7:0]', '0x00', 'RW', 'Y', 'Port data output (4th instance)'],
            ['', '', '', 'PortE', '3', '0x20', 'ConfigReg', '0x180', 'PullUp', '[3:0]', '0x0', 'RW', 'Y', 'Pull-up configuration (1st instance)'],
            ['', '', '', '', '', '', '', '', 'Drive', '[7:4]', '0x0', 'WO1', 'N', 'Write once after reset'],
            ['', '', '', '', '', '', 'StatusReg', '0x184', 'Level', '[7:0]', '0x0', 'RO', 'Y', 'Pin level status'],
            ['', '', '', '', '', '', 'EventReg', '0x188', 'EventFlag', '[0:0]', '0x0', 'W1S', 'Y', 'Write 1 sets flag'],
            ['', '', '', '', '', '', '', '', 'ClearFlag', '[1:1]', '0x0', 'W0S', 'Y', 'Write 0 sets flag (negated)'],
            ['PeripheralCtrl', '3', '0x30', '', '', '', 'PowerCtrl', '0x200', 'Enable', '[0:0]', '0x0', 'RW', 'Y', 'Power enable for peripheral'],
            ['', '', '', '', '', '', '', '', 'SleepMode', '[2:1]', '0x0', 'RC', 'Y', 'Read clears sleep mode'],
            ['', '', '', '', '', '', 'DMAConfig', '0x204', 'Channel', '[3:0]', '0x0', 'WRS', 'Y', 'Write as-is, read sets bits'],
            ['', '', '', '', '', '', 'DMAStatus', '0x208', 'Busy', '[0:0]', '0x0', 'RO', 'Y', 'DMA busy status'],
            ['', '', '', '', '', '', 'ErrorReg', '0x20C', 'Code', '[7:0]', '0x0', 'WOC', 'Y', 'Write clears, read error'],
            ['', '', '', '', '', '', 'TestReg', '0x210', 'ToggleBit', '[0:0]', '0x0', 'W0T', 'Y', 'Write 0 toggles bit'],
            ['', '', '', '', '', '', 'AdvIntReg', '0x214', 'Pending', '[3:0]', '0x0', 'W1CRS', 'Y', 'Write 1 clears matching, read sets all'],
            ['', '', '', '', '', '', '', '', 'Set', '[7:4]', '0x0', 'W0SRC', 'Y', 'Write 0 sets matching, read clears all'],
            ['', '', '', '', '', '', 'singleRepeat', '0x300', '0x10,0..3', '[31:0]', '0x55', 'RW', 'Y', 'single repeated sfr'],
            ['', '', '', '', '', '', 'singleSFR', '0x340', '', '[31:0]', '0xff', 'RW', 'Y', 'single sfr'],
            ['', '', '', '', '', '', 'singleField', '0x344', '', '[31:0]', '0xf00', 'RW', 'Y', 'single field sfr'],
            ['', '', '', '', '', '', '', '', 'field0', '[15:7]', '0x71', 'RW', 'Y', 'field'],
            ['', '', '', '', '', '', 'singleRepeatedField', '0x348', '0x4,0..1', '[31:0]', '0xf0', 'RW', 'Y', 'single repeated field sfr'],
            ['', '', '', '', '', '', '', '', 'field0', '[15:8]', '0xf', 'RW', 'Y', 'field0'],
            ['', '', '', '', '', '', '', '', 'field1', '[7:0]', '0', 'RW', 'Y', 'field1'],
            ['PeripheralCtrl2', '3', '0x30', '', '', '', 'PowerCtrl', '0x400', 'Enable', '[0:0]', '0x0', 'RW', 'Y', 'Power enable for peripheral'],
            ['', '', '', '', '', '', '', '', 'SleepMode', '[2:1]', '0x0', 'RC', 'Y', 'Read clears sleep mode'],
            ['', '', '', '', '', '', 'DMAConfig', '0x404', 'Channel', '[3:0]', '0x0', 'WRS', 'Y', 'Write as-is, read sets bits'],
            ['', '', '', '', '', '', 'DMAStatus', '0x408', 'Busy', '[0:0]', '0x0', 'RO', 'Y', 'DMA busy status'],
            ['', '', '', '', '', '', 'doubleint', '0x494', '', '[63:0]', '0', 'RW', 'Y', 'double int size sfr'],
            ['', '', '', '', '', '', 'long', '0x49C', '', '[127:0]', '0', 'RW', 'Y', 'long size sfr'],
            ['', '', '', '', '', '', 'longlong', '0x4AC', '', '[255:0]', '0', 'RW', 'Y', 'long long size sfr'],
            ['', '', '', '', '', '', 'custom512', '0x4CC', '', '[511:0]', '0', 'RW', 'Y', '512b size sfr']
        ]
        pd.DataFrame(complex_sfr_data).to_excel(writer, sheet_name='ComplexSFR', index=False, header=False)
    
    return test_xlsx


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SFR Excel to SystemRDL Converter")
    parser.add_argument("xlsx", nargs='?', help="Input XLSX file path (required unless --test)")
    parser.add_argument("--output-dir", "-o", help="Custom output directory (default: OUTPUT_2RDL)")
    parser.add_argument("--test", action='store_true', help="Run in test mode (create sample XLSX and convert)")
    
    args = parser.parse_args()
    
    if args.test:
        test_xlsx = create_test_xlsx()
        if test_xlsx is None:
            print("Test XLSX creation failed")
            sys.exit(1)
        converter = SFRToSystemRDL(test_xlsx, args.output_dir)
        converter.run()
    elif args.xlsx:
        converter = SFRToSystemRDL(args.xlsx, args.output_dir)
        converter.run()
    else:
        parser.print_help()
        sys.exit(1)