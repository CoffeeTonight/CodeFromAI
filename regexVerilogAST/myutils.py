from datetime import datetime
import os, sys, re, subprocess, json


def get_current_datetime():
    """
    현재 날짜와 시간을 문자열로 반환합니다.
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def get_full_path(path):
    """주어진 경로에서 환경 변수와 사용자 홈 디렉토리를 확장한 후, 절대 경로를 반환합니다."""
    # 환경 변수를 확장
    path = os.path.expandvars(path)

    # 사용자 홈 디렉토리를 확장
    path = os.path.expanduser(path)

    # 절대 경로로 변환
    absolute_path = os.path.abspath(path)

    return absolute_path


def remove_comments(code):
    """ Verilog 코드에서 주석을 제거합니다. """
    code = re.sub(r'//.*?\n', '\n', code)  # 한 줄 주석
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)  # 여러 줄 주석
    return code

def read_file(file_path, EXISTONLY=False):
    """주어진 파일 경로에서 Verilog 파일을 읽어 내용을 반환합니다.
    여러 인코딩을 고려하여 파일을 읽습니다.
    """
    if EXISTONLY:
        return os.path.exists(file_path)

    encodings_to_try = [
        'utf-8',
        'utf-16',
        'utf-32',
        'iso-8859-1',
        'windows-1252',
        'ascii',
        'macroman',
        'cp949',  # 한국어 인코딩
        'euc-kr'  # 한국어 인코딩
    ]

    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                return file.read()  # 파일 내용을 반환
        except (UnicodeDecodeError, FileNotFoundError) as e:
            print(f"Failed to read with encoding {encoding}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    raise ValueError("Could not read the file with any of the tried encodings.")