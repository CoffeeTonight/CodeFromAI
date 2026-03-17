import pandas as pd
import re
import logging
import sys
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import shutil
import argparse
from typing import Any, Dict


ACCESS_MAP = {
    'RW': {'sw': 'rw', 'hw': 'rw'},
    'RO': {'sw': 'r', 'hw': 'w'},
    'WO': {'sw': 'w', 'hw': 'r'},
    'W1C': {'sw': 'w', 'hw': 'r', 'onwrite': 'clr'},
    'RC': {'sw': 'r', 'hw': 'w', 'onread': 'clr'},
    'W0C': {'sw': 'w', 'hw': 'r', 'onwrite': 'clr'},
    'RS': {'sw': 'r', 'hw': 'w', 'onread': 'set'},
    'WC': {'sw': 'w', 'hw': 'r', 'onwrite': 'clr'},
    'WRC': {'sw': 'rw', 'hw': 'rw', 'onread': 'clr'},
    'WS': {'sw': 'w', 'hw': 'r', 'onwrite': 'set'},
    'W1T': {'sw': 'w', 'hw': 'r', 'onwrite': 'onetoggle'},
    'W0T': {'sw': 'w', 'hw': 'r', 'onwrite': 'zerotoggle'},
    'WO1': {'sw': 'w', 'hw': 'r', 'onwrite': 'oneset'},
    'W1S': {'sw': 'w', 'hw': 'r', 'onwrite': 'oneset'},
    'W0S': {'sw': 'w', 'hw': 'r', 'onwrite': 'zeroset'},
    'WRS': {'sw': 'rw', 'hw': 'rw', 'onread': 'set'},
    'W1CRS': {'sw': 'w', 'hw': 'r', 'onwrite': 'clr', 'onread': 'set'},
    'W0SRC': {'sw': 'w', 'hw': 'r', 'onwrite': 'clr', 'onread': 'set'},
}


def access_to_property(access: str) -> str:
    props = ACCESS_MAP.get(access.strip().upper(), {'sw': 'rw', 'hw': 'rw'})
    return ' '.join(f'{k} = {v};' for k, v in props.items())


def setup_logger(base_dir: str, excel_name: str):
    log_dir = Path(base_dir) / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{timestamp}_2RDL_{excel_name}.log"

    logger = logging.getLogger("SFRToRDL")
    logger.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

    logger.addHandler(console)
    logger.addHandler(fh)
    return logger


def to_addr_int(val) -> int:
    if pd.isna(val) or val == '':
        return 0
    s = str(val).strip().lower()
    if s.startswith(("0x", "h", "'h")):
        s = s.replace("0x", "").replace("h", "").replace("'", "")
    try:
        return int(s, 16)
    except ValueError:
        try:
            return int(s)
        except ValueError:
            return 0


class RdlContext:
    def __init__(self):
        self.lines = []
        self.indent_level = 0
        self.current_group = ""
        self.current_subgroup = ""
        self.current_reg = ""

    def add(self, text: str):
        indent = 4*" " * self.indent_level
        self.lines.append(indent + text)

    def push(self):
        self.indent_level += 1

    def pop(self):
        if self.indent_level > 0:
            self.indent_level -= 1

    def add_block_start(self, keyword: str, name: str = "", extra: str = ""):
        if extra:
            self.add(f"{keyword} {name}{extra} {{")
        elif name:
            self.add(f"{keyword} {name} {{")
        else:
            self.add(f"{keyword} {{")
        self.push()

    def close_block(self, suffix: str = ""):
        self.pop()
        if suffix:
            self.add(f"}} {suffix};")
        else:
            self.add("};")


class SFRToSystemRDL:
    def __init__(self, xlsx_path: str, output_dir: str = None):
        self.xlsx_path = Path(xlsx_path).resolve()
        self.excel_filename = self.xlsx_path.name

        self.base_dir = Path(output_dir) if output_dir else Path("OUTPUT_2RDL")
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.systemrdl_dir = self.base_dir / self.xlsx_path.stem
        self.systemrdl_dir.mkdir(exist_ok=True)

        self.logger = setup_logger(self.base_dir, self.excel_filename)
        self.logger.info(f"Starting conversion: {self.xlsx_path}")

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
                    name = cells[j + 1]
                    value = cells[j + 2]
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
                enabled = df[df['enable'].astype(str).str.lower().isin(['1', 'true', 'y', 'yes'])]
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
                df_full.iloc[header_idx + 1:].values,
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

    def preprocess_wide_bit_range(self, df: pd.DataFrame, bus_width: int = 32) -> pd.DataFrame:
        """
        Bit_Range가 bus_width보다 큰 레지스터를 배열화 전처리
        예: bus_width=32, [127:0] → Bit_Field를 '0x4,0..3'으로 변경
        """
        df = df.copy()  # 원본 보호

        for idx, row in df.iterrows():
            bit_range_str = str(row.get('Bit_Range', '')).strip()
            if not bit_range_str:
                continue

            # [msb:lsb] 파싱
            try:
                msb, lsb = map(int, re.findall(r'\[(\d+):(\d+)\]', bit_range_str)[0])
                bit_width = msb - lsb + 1
            except:
                continue  # 파싱 실패 → 그대로 둠

            if bit_width <= bus_width:
                continue  # bus_width 이하 → 그대로

            # 배열화 필요
            entry_count = (bit_width + bus_width - 1) // bus_width  # 올림 나눗셈
            stride_hex = hex(bus_width // 8)  # byte 단위 stride (32bit → 0x4)

            # Bit_Field를 '0x4,0..N-1' 형태로 강제 덮어쓰기
            new_bit_field = f"{stride_hex},{0}..{entry_count - 1}"
            df.at[idx, 'Bit_Field'] = new_bit_field

            # 기존 Bit_Range는 배열화된 첫 번째 필드의 범위로 조정 (필요 시)
            # 예: [127:0] → 첫 번째 필드 [31:0], 나머지는 자동 생성
            df.at[idx, 'Bit_Range'] = f"[{bus_width - 1}:0]"

            self.logger.info(
                f"전처리: {row.get('Register_Name', 'Unnamed')} "
                f"Bit_Range {bit_range_str} → 배열화 {new_bit_field} "
                f"(stride={stride_hex}, count={entry_count})"
            )

        return df

    def generate_sfr_addrmap(self, sheet_name: str, module_name: str, df: pd.DataFrame, bus_width: int = 32) -> str:
        self.logger.info(f"Generating RDL for {module_name} from sheet {sheet_name} ({len(df)} rows)")

        # 1. 넓은 Bit_Range 전처리 (bus_width보다 큰 경우 배열화)
        df = self.preprocess_wide_bit_range(df, bus_width)

        ctx = RdlContext()
        ctx.add(f"addrmap {module_name} #(")
        ctx.push()
        ctx.add(f"    longint BUS_WIDTH = {bus_width}")
        ctx.pop()
        ctx.add(") {")

        # Offset 정수 변환 & 정렬
        df['offset_int'] = df['Offset'].apply(to_addr_int)
        df = df.sort_values('offset_int').reset_index(drop=True).fillna('')

        active_repeat = None  # reg 레벨 반복 그룹 상태

        for idx, row in df.iterrows():
            reg_name = str(row.get('Register_Name', '')).strip()
            if not reg_name:
                continue

            offset_int = row['offset_int']
            bit_field_str = str(row.get('Bit_Field', '')).strip()
            bit_range = str(row.get('Bit_Range', '')).strip() or "[31:0]"
            access = str(row.get('Access_Type', 'RW')).strip()
            reset_val = self.parse_verilog_hex(str(row.get('Default_Value', '0')))
            desc = str(row.get('Description', '')).strip().replace('"', '\\"')

            group_name = str(row.get('Group_Name', '')).strip()
            subgroup_name = str(row.get('Subgroup_Name', '')).strip()

            # ────────────────────────────────────────
            # 그룹 열기 (Repeat Count 반영)
            # ────────────────────────────────────────
            group_repeat = 1
            if 'Group_Repeat_Count' in row and pd.notna(row['Group_Repeat_Count']):
                repeat_val = str(row['Group_Repeat_Count']).strip()
                if '..' in repeat_val:
                    try:
                        start, end = map(int, repeat_val.split('..'))
                        group_repeat = max(1, end - start + 1)
                    except:
                        pass
                elif repeat_val.isdigit():
                    group_repeat = int(repeat_val)

            if group_name and group_name != ctx.current_group:
                while ctx.indent_level > 0:
                    ctx.close_block()
                ctx.current_group = group_name
                ctx.current_subgroup = ""
                ctx.current_reg = ""
                ctx.add_block_start("addrmap", group_name, f"[{group_repeat}]" if group_repeat > 1 else "")

            # ────────────────────────────────────────
            # 서브그룹 열기 (Repeat Count 반영)
            # ────────────────────────────────────────
            subgroup_repeat = 1
            if 'Subgroup_Repeat_Count' in row and pd.notna(row['Subgroup_Repeat_Count']):
                repeat_val = str(row['Subgroup_Repeat_Count']).strip()
                if '..' in repeat_val:
                    try:
                        start, end = map(int, repeat_val.split('..'))
                        subgroup_repeat = max(1, end - start + 1)
                    except:
                        pass
                elif repeat_val.isdigit():
                    subgroup_repeat = int(repeat_val)

            if subgroup_name and subgroup_name != ctx.current_subgroup:
                while ctx.indent_level > 1:
                    ctx.close_block()
                ctx.current_subgroup = subgroup_name
                ctx.current_reg = ""
                ctx.add_block_start("regfile", subgroup_name, f"[{subgroup_repeat}]" if subgroup_repeat > 1 else "")

            # ────────────────────────────────────────
            # reg 레벨 반복 시작 감지 (Bit_Field 패턴)
            # ────────────────────────────────────────
            is_repeat_start = False
            stride = 4
            repeat_count = 1
            if ',' in bit_field_str and '..' in bit_field_str:
                parts = bit_field_str.split(',', 1)
                if len(parts) == 2:
                    stride_str, range_part = [p.strip() for p in parts]
                    stride = to_addr_int(stride_str) or 4
                    try:
                        start, end = map(int, range_part.split('..'))
                        repeat_count = max(1, end - start + 1)
                        is_repeat_start = repeat_count > 1
                    except:
                        pass

            if is_repeat_start:
                if active_repeat and active_repeat['index'] < active_repeat['count']:
                    self.logger.warning(f"미완성 repeat 그룹: {active_repeat['reg_name']}")
                    ctx.add(f"reg {active_repeat['reg_name']}[{active_repeat['count']}] {{")
                    ctx.push()
                    for f in active_repeat['fields']:
                        ctx.add(f"    field {{ {f['props']} reset = {f['reset']}; }} {f['name']} {f['range']};")
                    ctx.close_block(f"@ {hex(active_repeat['base_offset'])}")
                active_repeat = {
                    'reg_name': reg_name,
                    'base_offset': offset_int,
                    'stride': stride,
                    'count': repeat_count,
                    'index': 0,
                    'fields': []
                }
                continue

            # ────────────────────────────────────────
            # 반복 그룹 이어가기
            # ────────────────────────────────────────
            if active_repeat:
                expected = active_repeat['base_offset'] + active_repeat['index'] * active_repeat['stride']
                if offset_int == expected:
                    field_name = bit_field_str if bit_field_str.isidentifier() else "data"
                    props = access_to_property(access)
                    active_repeat['fields'].append({
                        'name': field_name,
                        'range': bit_range,
                        'props': props,
                        'reset': reset_val
                    })
                    active_repeat['index'] += 1

                    if active_repeat['index'] >= active_repeat['count']:
                        ctx.add(f"reg {active_repeat['reg_name']}[{active_repeat['count']}] {{")
                        ctx.push()

                        # regwidth 추가 (필요할 때만 - bus_width와 다를 때)
                        if active_repeat['fields']:
                            first_range = active_repeat['fields'][0]['range']
                            try:
                                match = re.search(r'\[(\d+):(\d+)\]', first_range)
                                if match:
                                    msb = int(match.group(1))
                                    lsb = int(match.group(2))
                                    bit_width = msb - lsb + 1
                                    if bit_width > bus_width:
                                        ctx.add(f"    regwidth = {bit_width};")
                            except:
                                pass

                        for f in active_repeat['fields']:
                            field_line = f"    field {{ {f['props']} reset = {f['reset']};"
                            if desc:
                                field_line += f" desc = \"{desc}\";"
                            field_line += f" }} {f['name']} {f['range']};"
                            ctx.add(field_line)

                        ctx.close_block(f"@ {hex(active_repeat['base_offset'])}")
                        active_repeat = None
                    continue
                else:
                    self.logger.warning(f"Repeat offset mismatch: {hex(offset_int)} (expected {hex(expected)})")
                    active_repeat = None

            # ────────────────────────────────────────
            # 일반 레지스터 (여러 필드 지원)
            # ────────────────────────────────────────
            if reg_name != ctx.current_reg:
                if ctx.current_reg:
                    ctx.close_block(f"@ {hex(ctx.current_reg_offset)}")
                ctx.current_reg = reg_name
                ctx.current_reg_offset = offset_int
                ctx.add_block_start("reg")

                # regwidth 추가 (필요할 때만 - bus_width와 다를 때)
                bit_width = 32
                if bit_range and bit_range.strip():
                    try:
                        match = re.search(r'\[(\d+):(\d+)\]', bit_range)
                        if match:
                            msb = int(match.group(1))
                            lsb = int(match.group(2))
                            bit_width = msb - lsb + 1
                        else:
                            bit_width = bus_width
                    except:
                        bit_width = bus_width

                # regwidth 추가 조건: bus_width와 다를 때만
                if bit_width > bus_width:
                    ctx.add(f"    regwidth = {bit_width};")

            if bit_range:
                field_name = bit_field_str if bit_field_str.isidentifier() else "data"
                props = access_to_property(access)
                field_line = f"    field {{ {props} reset = {reset_val};"
                if desc:
                    field_line += f" desc = \"{desc}\";"
                field_line += f" }} {field_name} {bit_range};"
                ctx.add(field_line)

        # ────────────────────────────────────────
        # 마지막 레지스터 및 블록 닫기
        # ────────────────────────────────────────
        if ctx.current_reg:
            ctx.close_block(f"@ {hex(ctx.current_reg_offset)}")

        while ctx.indent_level > 0:
            ctx.close_block()

        ctx.add("};")

        content = "\n".join(ctx.lines)
        if len(ctx.lines) <= 6:
            content = f"addrmap {module_name} {{\n    // WARNING: 내용 거의 없음\n}};\n" + content

        return content

    def run(self):
        self.logger.info("=== Conversion Started ===")
        try:
            self.load_sheets()

            module_to_sheet = {}
            module_to_bw = {}
            prev_module = ""

            for mm_name, mm_df in self.memorymap_dfs.items():
                for _, row in tqdm(mm_df.iterrows(), total=len(mm_df), desc=f"Mapping {mm_name}"):
                    if str(row.get('enable', '')).lower() not in ['1', 'true', 'y', 'yes']:
                        continue
                    module = str(row.get('module', '')).strip() or prev_module
                    prev_module = module
                    sheet = str(row.get('sheet', '')).strip()
                    bw = int(row.get('bus_data_width', 32))
                    if module and sheet:
                        module_to_sheet[module] = sheet
                        module_to_bw[module] = bw

            top_rdl = self.generate_top_memorymap()
            (self.systemrdl_dir / "soc_top.rdl").write_text(top_rdl, encoding="utf-8")
            self.logger.info("soc_top.rdl saved")

            for module, sheet in module_to_sheet.items():
                if sheet not in self.sfr_dfs:
                    continue
                df = self.sfr_dfs[sheet]
                bw = module_to_bw.get(module, 32)
                rdl_content = self.generate_sfr_addrmap(sheet, module, df, bw)
                path = self.systemrdl_dir / f"{module}.rdl"
                path.write_text(rdl_content, encoding="utf-8")
                self.logger.info(f"Saved {path} (sheet={sheet}, bus_width={bw})")

            self.logger.info("=== Conversion Finished ===")
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
            ['', '', '', '', '', '', 'InterruptCtrl', '0x18', '0x4, 0..1', '', '0xF', 'RW', 'Y', 'Interrupt mask bits'],
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
    parser.add_argument("xlsx", nargs='?', help="Input XLSX file path")
    parser.add_argument("--output-dir", "-o")
    parser.add_argument("--test", action='store_true')
    args = parser.parse_args()

    if args.test:
        test_xlsx = create_test_xlsx()
        converter = SFRToSystemRDL(test_xlsx, args.output_dir)
        converter.run()
    elif args.xlsx:
        converter = SFRToSystemRDL(args.xlsx, args.output_dir)
        converter.run()
    else:
        parser.print_help()
        sys.exit(1)