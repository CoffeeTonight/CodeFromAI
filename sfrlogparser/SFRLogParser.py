from typing import List, Dict
from collections import defaultdict
import re
import pandas as pd

class SFRLogParser:
    """
    SFR Bitfield 검증 로그 파싱 및 pandas 기반 리포트 클래스
    """
    
    def __init__(self):
        self.parsed_logs: List[Dict] = []
        self.grouped_logs = None
        self.judgement = None

    def parse_file(self, log_file_path: str) -> List[Dict]:
        """로그 파일 파싱"""
        self.parsed_logs = []
        with open(log_file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                parsed = self._parse_line(line)
                if parsed:
                    parsed['line_number'] = line_num
                    self.parsed_logs.append(parsed)
        
        print(f"[SFRLogParser] 총 {len(self.parsed_logs)}개의 로그를 파싱했습니다.")
        return self.parsed_logs

    def _parse_line(self, line: str) -> Dict:
        line = line.strip()
        if not line or line.startswith('#'):
            return None

        result = {}

        # 시간 및 버전 추출
        time_match = re.search(r'\[(.*?)\]\[(.*?)\]', line)
        if time_match:
            result['tool_version'] = time_match.group(1)
            result['timestamp'] = time_match.group(2)

        # | 구분자 파싱
        content = line.split(']', 1)[-1] if ']' in line else line
        parts = [p.strip() for p in content.split('|') if p.strip()]

        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                result[key.strip()] = value.strip()

        # 타입 변환
        for key in ['GRP', 'NUM', 'STEP']:   # SEQ → NUM으로 변경
            if key in result:
                try:
                    result[key] = int(result[key])
                except ValueError:
                    pass

        return result

    def group_by_test_and_field(self):
        """GRP → NUM → STEP 구조로 그룹핑"""
        if not self.parsed_logs:
            return {}

        grouped = defaultdict(lambda: defaultdict(dict))
        for log in self.parsed_logs:
            grp = log.get('GRP', 0)
            num = log.get('NUM', 0)        # SEQ → NUM 변경
            step = log.get('STEP', 0)
            grouped[grp][num][step] = log
        
        self.grouped_logs = dict(grouped)
        return self.grouped_logs

    def judge_pass_fail(self):
        """NUM (bit field) 단위로 pass/fail 판단"""
        if self.grouped_logs is None:
            self.group_by_test_and_field()

        judgement = defaultdict(dict)
        for grp_id, num_dict in self.grouped_logs.items():
            for num_id, step_dict in num_dict.items():
                attr = step_dict.get(0, {}).get('ATTR', 'UNKNOWN')
                is_pass = True
                reason = "OK"

                if attr == "RW":
                    if 2 in step_dict and step_dict[2].get('DATA') == '0x00000000':
                        is_pass = False
                        reason = "RW write not reflected"
                elif attr in ["W1C", "W0C"]:
                    for s in step_dict:
                        if step_dict[s].get('OP') == 'R' and step_dict[s].get('DATA') != '0x00000000':
                            is_pass = False
                            reason = "Clear failed"
                            break

                judgement[grp_id][num_id] = {
                    "attr": attr,
                    "pass": is_pass,
                    "reason": reason
                }
        self.judgement = dict(judgement)
        return self.judgement

    def generate_report(self):
        """pandas를 사용한 예쁜 테이블 리포트"""
        if self.judgement is None:
            self.judge_pass_fail()

        data = []
        for grp in sorted(self.judgement.keys()):
            row = {"GRP": f"GRP {grp}"}
            total = 0
            passed = 0
            attr_stats = defaultdict(lambda: {"count": 0, "passed": 0})

            for seq_info in self.judgement[grp].values():
                attr = seq_info["attr"]
                attr_stats[attr]["count"] += 1
                if seq_info["pass"]:
                    attr_stats[attr]["passed"] += 1
                total += 1
                passed += 1 if seq_info["pass"] else 0

            for attr in sorted(attr_stats.keys()):
                c = attr_stats[attr]["count"]
                p = attr_stats[attr]["passed"]
                row[attr] = f"{p}/{c}" if c > 0 else "-"

            row["Total"] = total
            row["Passed"] = passed
            row["Pass Rate"] = f"{passed/total:.1%}" if total > 0 else "-"
            data.append(row)

        df = pd.DataFrame(data)
        df = df.fillna("-")

        # 컬럼 순서 조정
        cols = ["GRP"] + [col for col in df.columns if col not in ["GRP", "Total", "Passed", "Pass Rate"]] + ["Total", "Passed", "Pass Rate"]
        df = df[cols]

        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.colheader_justify', 'center')

        print("\n" + "="*100)
        print("                  SFR Bitfield Verification Report")
        print("="*100)
        print(df.to_string(index=False))
        print("="*100)

        total_fields = df['Total'].sum()
        total_passed = df['Passed'].sum()
        rate = f"{total_passed/total_fields:.1%}" if total_fields > 0 else "-"
        print(f"Total Fields Tested : {total_fields}")
        print(f"Total Passed        : {total_passed}")
        print(f"Overall Pass Rate   : {rate}")
        print("="*100)

    def generate_sample_log(self, filename: str = "sample_verification.log"):
        """샘플 로그 생성"""
        sample = [
            '[thistoolname_v0.1][2026-03-30 19:45:12.123]|GRP=1|NUM=2|STEP=0|ATTR=RW|OP=R|ADDR=0x10000010|DATA=0x00000005|LSBW=[0,4]|REG=CTRL.INT_EN[3:0]',
            '[thistoolname_v0.1][2026-03-30 19:45:12.456]|GRP=1|NUM=2|STEP=1|OP=W|DATA=0xFFFFFFFA',
            '[thistoolname_v0.1][2026-03-30 19:45:12.789]|GRP=1|NUM=2|STEP=2|OP=R|DATA=0xFFFFFFFA',
            '[thistoolname_v0.1][2026-03-30 19:45:13.012]|GRP=1|NUM=2|STEP=3|OP=W|DATA=0x00000005',
            '[thistoolname_v0.1][2026-03-30 19:45:13.345]|GRP=1|NUM=2|STEP=4|OP=R|DATA=0x00000005',
            '[thistoolname_v0.1][2026-03-30 19:46:05.678]|GRP=2|NUM=4|STEP=0|ATTR=W1C|OP=R|ADDR=0x10000020|DATA=0x00000001|LSBW=[15,1]|REG=IRQ_FLAGS.ERR[15]',
            '[thistoolname_v0.1][2026-03-30 19:46:05.901]|GRP=2|NUM=4|STEP=1|OP=W|DATA=0x00008000',
            '[thistoolname_v0.1][2026-03-30 19:46:06.234]|GRP=2|NUM=4|STEP=2|OP=R|DATA=0x00000000',
        ]
        with open(filename, 'w', encoding='utf-8') as f:
            for line in sample:
                f.write(line + '\n')
        print(f"샘플 로그 파일 생성 완료: {filename}")


# ==================== 사용 예시 ====================
if __name__ == "__main__":
    parser = SFRLogParser()
    
    # 샘플 로그 생성
    parser.generate_sample_log("sample_verification.log")
    
    # 파싱 및 분석
    parser.parse_file("sample_verification.log")
    parser.group_by_test_and_field()
    parser.judge_pass_fail()
    
    # pandas 리포트 출력
    parser.generate_report()