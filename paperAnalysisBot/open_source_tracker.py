# open_source_tracker.py
import json
import re
from pathlib import Path
from typing import List, Dict
from config import Config
from datetime import datetime

class OpenSourceTracker:
    def __init__(self):
        self.db_path = Config.OPEN_SOURCE_DB_PATH
        self.data = self._load_data()

    def _load_data(self) -> List[Dict]:
        """jsonl 파일 로드"""
        if not self.db_path.exists():
            return []
        data = []
        with open(self.db_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        return data

    def _save_data(self):
        """jsonl 파일 저장"""
        with open(self.db_path, 'w', encoding='utf-8') as f:
            for item in self.data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def extract_github_links(self, pdf_path: Path) -> List[str]:
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
            return list(set(links))  # 중복 제거
        except Exception as e:
            print(f"GitHub 추출 실패 ({pdf_path.name}): {e}")
            return []

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

            links = self.extract_github_links(pdf_path)
            if links:
                entry = {
                    "title": title,
                    "pdf_path": str(pdf_path),
                    "github_links": links,
                    "updated_at": datetime.now().isoformat()
                }
                self.data.append(entry)
                updated += 1
                print(f"오픈소스 발견: {title} → {len(links)}개 링크")

        if updated > 0:
            self._save_data()
        print(f"{updated}개 새로운 오픈소스 프로젝트 추가 완료")
        return updated

    def get_open_source_list(self) -> List[Dict]:
        """현재 저장된 오픈소스 목록 반환"""
        return self.data

    def get_open_source_summary(self) -> str:
        """프롬프트용 요약 문자열 생성"""
        if not self.data:
            return "현재 공개된 오픈소스 프로젝트가 없습니다."

        summary = "공개된 오픈소스 프로젝트:\n"
        for item in self.data:
            summary += f"- {item['title']}\n"
            for link in item['github_links']:
                summary += f"  → {link}\n"
        return summary


# __main__ 테스트
if __name__ == "__main__":
    print("=== Open Source Tracker 테스트 시작 ===")
    tracker = OpenSourceTracker()

    print("오픈소스 업데이트 시작...")
    tracker.update_from_papers()

    print("\n현재 오픈소스 목록:")
    for item in tracker.get_open_source_list():
        print(f"- {item['title']}")
        for link in item['github_links']:
            print(f"  → {link}")

    print("\n요약 문자열:")
    print(tracker.get_open_source_summary())

    print("\n테스트 완료!")