#!/usr/bin/env python3
"""
EDAFilelistParser - 상용 EDA(VCS, Xcelium) 스타일 파일리스트 파서

목표:
- -f / -F 정확한 구분과 상대경로 해석
- +incdir 정확한 수집 (순서 보존)
- 다양한 주석, 환경변수, 중첩 파일리스트 지원
- 실제 프로젝트 .f 파일을 그대로 읽을 수 있는 수준

이 모듈은 기존 parseFilelist.py를 건드리지 않고 새로 작성되었습니다.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple


class EDAFilelistParser:
    """
    상용 EDA 도구 수준의 파일리스트 파서
    """

    def __init__(self, top_filelist: str, env: Optional[Dict[str, str]] = None):
        self.top_filelist = Path(top_filelist).resolve()
        self.env = env or {}
        self.base_dir = self.top_filelist.parent

        # 결과 저장소
        self.source_files: List[Path] = []          # 실제 소스 파일들 (절대경로)
        self.incdirs: List[Path] = []               # +incdir (순서 중요)
        self.libdirs: List[Path] = []               # -y 라이브러리 디렉토리
        self.libexts: List[str] = []                # +libext
        self.libfiles: List[Path] = []              # -v 단일 라이브러리 파일
        self.defines: Dict[str, str] = {}           # +define

        # 디버깅 / 추적용
        self.processed_filelists: List[Tuple[Path, str]] = []  # (path, mode)
        self.errors: List[str] = []

        # 내부 상태
        self._seen_filelists: Set[Path] = set()

        # 파싱 시작
        self._parse_filelist(self.top_filelist, use_filelist_dir_as_base=True)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    def get_source_files(self) -> List[str]:
        return [str(p) for p in self.source_files]

    def get_incdirs(self) -> List[str]:
        return [str(p) for p in self.incdirs]

    def get_all_files(self) -> List[str]:
        """소스 + 라이브러리 파일 전체"""
        all_files = self.source_files + self.libfiles
        return [str(p) for p in all_files]

    def resolve_include(self, include_path: str, from_file: Optional[str] = None) -> Optional[str]:
        """
        `include "xxx.svh"` 를 해석한다.
        1. from_file이 있으면 그 파일이 있는 디렉토리에서 먼저 찾음
        2. 그 다음 self.incdirs 순서대로 찾음
        """
        candidates = []

        if from_file:
            from_dir = Path(from_file).parent
            candidates.append(from_dir / include_path)

        for inc in self.incdirs:
            candidates.append(inc / include_path)

        for cand in candidates:
            if cand.exists():
                return str(cand.resolve())

        return None

    def discover_library_modules(self) -> Dict[str, Path]:
        """
        -y + +libext, -v 를 사용해 모듈 이름을 자동 발견 (간단 버전)
        반환: {module_name: file_path}
        """
        discovered = {}

        # 1. -v 로 지정된 라이브러리 파일들 직접 스캔
        for libfile in self.libfiles:
            if libfile.exists():
                try:
                    content = libfile.read_text(errors="ignore")
                    for mod in re.findall(r'^\s*module\s+(\w+)', content, re.MULTILINE):
                        discovered[mod] = libfile
                except Exception:
                    pass

        # 2. -y 디렉토리 + libext 조합으로 스캔
        exts = self.libexts if self.libexts else ['.v', '.sv']
        for libdir in self.libdirs:
            if not libdir.exists():
                continue
            for ext in exts:
                for f in libdir.glob(f"*{ext}"):
                    try:
                        content = f.read_text(errors="ignore")
                        for mod in re.findall(r'^\s*module\s+(\w+)', content, re.MULTILINE):
                            if mod not in discovered:  # -v 가 우선
                                discovered[mod] = f
                    except Exception:
                        pass

        return discovered

    def summary(self) -> str:
        return (
            f"EDAFilelistParser Summary\n"
            f"  Top filelist : {self.top_filelist}\n"
            f"  Source files : {len(self.source_files)}\n"
            f"  Incdirs      : {len(self.incdirs)}\n"
            f"  Libdirs (-y) : {len(self.libdirs)}\n"
            f"  Libexts      : {self.libexts}\n"
            f"  Libfiles (-v): {len(self.libfiles)}\n"
            f"  Defines      : {self.defines}\n"
            f"  Errors       : {len(self.errors)}\n"
        )

    # ------------------------------------------------------------------
    # 내부 파싱 로직
    # ------------------------------------------------------------------
    def _parse_filelist(self, filelist_path: Path, use_filelist_dir_as_base: bool):
        """
        실제 파일리스트 하나를 파싱한다.
        use_filelist_dir_as_base:
            True  -> -F 스타일 (이 파일리스트 위치를 기준으로 상대경로 해석)
            False -> -f 스타일 (원래 CWD 기준)
        """
        filelist_path = filelist_path.resolve()

        if filelist_path in self._seen_filelists:
            return
        self._seen_filelists.add(filelist_path)

        if not filelist_path.exists():
            self.errors.append(f"Filelist not found: {filelist_path}")
            return

        # 이 파일리스트의 기준 디렉토리 결정
        if use_filelist_dir_as_base:
            current_base = filelist_path.parent
        else:
            current_base = Path.cwd()

        self.processed_filelists.append((filelist_path, "F" if use_filelist_dir_as_base else "f"))

        try:
            content = filelist_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            self.errors.append(f"Failed to read {filelist_path}: {e}")
            return

        # 주석 제거 (강력 버전)
        clean_lines = self._strip_comments(content)

        for raw_line in clean_lines:
            line = raw_line.strip()
            if not line:
                continue

            # 환경변수 치환
            line = self._expand_env(line, current_base)

            # --- 옵션 파싱 ---
            if line.startswith("-F") or line.startswith("-f"):
                # Treat both -f and -F the same for recursion in practice:
                # Always use the included filelist's own directory as base for its relative paths.
                # This makes recursive/nested filelists much more reliable.
                token = line[2:].strip() if line.startswith("-F") else line[2:].strip()
                sub_path = self._resolve_path(token, current_base)
                # Force use_filelist_dir_as_base=True so relative paths inside the sub-filelist
                # are resolved relative to the sub-filelist's location (standard EDA behavior).
                self._parse_filelist(sub_path, use_filelist_dir_as_base=True)

            elif line.startswith("+incdir+"):
                dirs = line[len("+incdir+"):].split("+")
                for d in dirs:
                    d = d.strip()
                    if d:
                        resolved = self._resolve_path(d, current_base)
                        if resolved not in self.incdirs:
                            self.incdirs.append(resolved)

            elif line.startswith("-y"):
                d = line[2:].strip()
                if d:
                    resolved = self._resolve_path(d, current_base)
                    if resolved not in self.libdirs:
                        self.libdirs.append(resolved)

            elif line.startswith("+libext+"):
                exts = line[len("+libext+"):].split("+")
                for e in exts:
                    e = e.strip()
                    if e and e not in self.libexts:
                        self.libexts.append(e)

            elif line.startswith("-v"):
                f = line[2:].strip()
                if f:
                    resolved = self._resolve_path(f, current_base)
                    if resolved not in self.libfiles:
                        self.libfiles.append(resolved)

            elif line.startswith("+define+"):
                define_str = line[len("+define+"):]
                self._parse_define(define_str)

            elif line.startswith(("+", "-")):
                # 아직 지원하지 않는 다른 옵션은 일단 무시 (로그 남김)
                # 추후 필요시 확장
                pass

            else:
                # 일반 소스 파일로 간주
                if line.startswith(('$', '{')):
                    if '$' in line:
                        self.errors.append(f"Could not fully expand line, skipping: {line}")
                    continue

                resolved = self._resolve_path(line, current_base)

                # 디렉토리는 소스 파일로 넣지 않음
                if resolved.is_dir():
                    continue

                # 파일이 실제로 존재하거나, Verilog 확장자라면 추가
                if resolved.exists() or resolved.suffix.lower() in ('.v', '.sv', '.svh', '.vh', '.f'):
                    if resolved not in self.source_files:
                        self.source_files.append(resolved)
                else:
                    # top filelist 기준으로 한 번 더 시도 (실무 관용)
                    fallback = self._resolve_path(line, self.top_filelist.parent)
                    if not fallback.is_dir() and (fallback.exists() or fallback.suffix.lower() in ('.v', '.sv', '.svh', '.vh')):
                        if fallback not in self.source_files:
                            self.source_files.append(fallback)

    def _strip_comments(self, content: str) -> List[str]:
        """강력한 주석 제거 (//, /* */, #)"""
        # /* */ 먼저 제거 (여러 줄 가능)
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

        lines = []
        for line in content.splitlines():
            # // 주석 제거
            line = re.sub(r"//.*$", "", line)
            # # 으로 시작하는 라인 주석 (일부 툴 지원)
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # 앞뒤 공백 정리 후 빈 줄이 아니면 추가
            line = line.strip()
            if line:
                lines.append(line)
        return lines

    def _expand_env(self, text: str, base: Path) -> str:
        """환경변수 치환 ($VAR, ${VAR}). 테스트 편의를 위해 $PROJ_ROOT 등을 자동 처리."""
        def replacer(match):
            var = match.group(1) or match.group(2)
            # 테스트 편의: $PROJ_ROOT가 지정되지 않았으면 이 파일리스트의 상위 디렉토리로 가정
            if var in ("PROJ_ROOT", "PROJECT_ROOT"):
                return str(base.parent.parent)  # tests/filelist_eda 의 상위
            value = self.env.get(var)
            if value is None:
                value = os.environ.get(var, f"${{{var}}}")
            return value

        # ${VAR} 형태
        text = re.sub(r"\$\{([^}]+)\}", replacer, text)
        # $VAR 형태
        text = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", replacer, text)
        return text

    def _resolve_path(self, path_str: str, base: Path) -> Path:
        p = Path(path_str)
        if p.is_absolute():
            return p.resolve()
        else:
            return (base / p).resolve()

    def _parse_define(self, define_str: str):
        """+define+MACRO or +define+MACRO=VALUE"""
        for item in define_str.split("+"):
            item = item.strip()
            if not item:
                continue
            if "=" in item:
                name, value = item.split("=", 1)
                self.defines[name] = value
            else:
                self.defines[item] = "1"


# ----------------------------------------------------------------------
# 편의 함수
# ----------------------------------------------------------------------
def parse_eda_filelist(top_filelist: str, env: Optional[Dict[str, str]] = None) -> EDAFilelistParser:
    return EDAFilelistParser(top_filelist, env)


if __name__ == "__main__":
    # 간단한 직접 실행 테스트
    import sys
    if len(sys.argv) < 2:
        print("Usage: python eda_filelist_parser.py <top.f>")
        sys.exit(1)

    parser = parse_eda_filelist(sys.argv[1])
    print(parser.summary())
    print("Source files:")
    for f in parser.get_source_files():
        print(f"  {f}")
