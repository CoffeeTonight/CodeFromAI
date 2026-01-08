# core/open_source_tracker.py
import json
import re
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from core.config import Config
from core.utils import get_logger  # 중앙 로거 가져오기

logger = get_logger("OpenSourceTracker")  # 모듈 이름으로 구분

class OpenSourceTracker:
    def __init__(self):
        self.db_path = Config.OPEN_SOURCE_DB_PATH
        self.data = self._load_data()

    def _load_data(self) -> List[Dict]:
        """jsonl 파일 로드"""
        if not self.db_path.exists():
            logger.info("오픈소스 DB 파일 없음 → 빈 리스트 반환")
            return []

        data = []
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if isinstance(entry, dict):
                            data.append(entry)
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 파싱 실패 (라인 {line_num}): {e}")
        except Exception as e:
            logger.error(f"오픈소스 DB 로드 실패: {e}")

        logger.info(f"오픈소스 DB 로드 완료: {len(data)}개 항목")
        return data

    def _save_data(self):
        """jsonl 파일 저장"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                for item in self.data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            logger.info(f"오픈소스 DB 저장 완료: {len(self.data)}개 항목")
        except Exception as e:
            logger.error(f"오픈소스 DB 저장 실패: {e}")

    def _extract_github_links(self, pdf_path: Path) -> List[str]:
        """PDF에서 GitHub 링크 추출"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()

            pattern = r'https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'
            links = re.findall(pattern, text)
            unique_links = list(set(links))
            if unique_links:
                logger.info(f"GitHub 링크 발견 ({pdf_path.name}): {len(unique_links)}개")
            return unique_links
        except Exception as e:
            logger.warning(f"GitHub 추출 실패 ({pdf_path.name}): {e}")
            return []

    def _save_open_source_info(self, entry: Dict):
        self.data.append(entry)
        logger.debug(f"오픈소스 정보 추가: {entry.get('title')}")

    def update_from_papers(self):
        """paper 폴더의 모든 PDF에서 오픈소스 추출 및 업데이트"""
        updated = 0
        existing_titles = {item.get("title", "") for item in self.data}

        for pdf_path in Config.PAPER_DIR.iterdir():
            if pdf_path.suffix.lower() != ".pdf":
                continue

            title = pdf_path.stem
            if title in existing_titles:
                continue

            links = self._extract_github_links(pdf_path)
            if links:
                entry = {
                    "title": title,
                    "pdf_path": str(pdf_path),
                    "github_links": links,
                    "updated_at": datetime.now().isoformat()
                }
                self._save_open_source_info(entry)
                updated += 1

        if updated > 0:
            self._save_data()

        logger.info(f"{updated}개 새로운 오픈소스 프로젝트 추가 완료")
        return updated

    def get_open_source_list(self) -> List[Dict]:
        """현재 저장된 오픈소스 목록 반환"""
        logger.debug(f"오픈소스 목록 요청: {len(self.data)}개")
        return self.data

    def get_open_source_summary(self) -> str:
        """프롬프트용 요약 문자열 생성"""
        if not self.data:
            summary = "현재 공개된 오픈소스 프로젝트가 없습니다."
            logger.info("오픈소스 요약: 없음")
            return summary

        summary = "공개된 오픈소스 프로젝트:\n"
        for item in self.data:
            summary += f"- {item['title']}\n"
            for link in item['github_links']:
                summary += f"  → {link}\n"

        logger.info(f"오픈소스 요약 생성 완료: {len(self.data)}개 프로젝트")
        return summary


# 테스트
if __name__ == "__main__":
    logger.info("=== Open Source Tracker 테스트 시작 ===")

    tracker = OpenSourceTracker()

    logger.info("오픈소스 업데이트 시작...")
    tracker.update_from_papers()

    logger.info("\n현재 오픈소스 목록:")
    for item in tracker.get_open_source_list():
        logger.info(f"- {item['title']}")
        for link in item['github_links']:
            logger.info(f"  → {link}")

    logger.info("\n요약 문자열:")
    logger.info(tracker.get_open_source_summary())

    logger.info("\n테스트 완료!")