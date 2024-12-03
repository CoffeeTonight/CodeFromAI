import datetime
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