# core/paper_manager.py
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import arxiv
from config import Config
import urllib.request  # 이 줄 추가!
import ssl  # 이 줄도 추가 (SSL 우회용)

class PaperManager:
    def __init__(self):
        self.paper_dir = Config.PAPER_DIR
        self.history_path = Config.DOWNLOAD_HISTORY_PATH
        self.open_source_path = Config.OPEN_SOURCE_DB_PATH
        self.download_history = self._load_download_history()

        # 핵심: 빈 리스트일 때도 dict 리스트로 초기화
        if not self.download_history:
            self.download_history = []

    def _load_download_history(self) -> List[Dict]:
        """jsonl 형식으로 다운로드 히스토리 로드 (빈 파일/신규 시작 완벽 지원)"""
        history = []
        if self.history_path.exists():
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if isinstance(entry, dict):
                                history.append(entry)
                            else:
                                print(f"손상된 엔트리 무시 (line {line_num}): 타입 오류")
                        except json.JSONDecodeError as e:
                            print(f"손상된 줄 무시 (line {line_num}): {e} - {line}")
            except Exception as e:
                print(f"히스토리 파일 읽기 실패: {e}")
        else:
            print("다운로드 히스토리 파일 없음 - 새로 생성됩니다.")

        return history

    def _save_download_history(self, entry: Dict):
        """jsonl에 한 줄 추가 (파일/폴더 자동 생성)"""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _extract_github_links(self, pdf_path: Path) -> List[str]:
        """PDF 텍스트에서 GitHub 링크 추출"""
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

    def _save_open_source_info(self, entry: Dict):
        """오픈소스 정보 jsonl에 저장"""
        with open(self.open_source_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def download_from_arxiv(self, query: Optional[str] = None, max_results: int = 30) -> int:
        """arXiv에서 논문 다운로드 (중복 방지 + 히스토리 저장 + SSL 우회)"""
        query = query or Config.DEFAULT_ARXIV_QUERY
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        downloaded = 0
        for result in search.results():
            arxiv_id = result.entry_id.split('/')[-1]

            # 중복 체크
            if any(e.get("arxiv_id") == arxiv_id for e in self.download_history):
                continue

            filename = self.paper_dir / f"{arxiv_id}.pdf"
            try:
                # SSL 인증서 문제 우회 (Windows에서 필수!)
                import ssl
                ssl_context = ssl._create_unverified_context()
                with urllib.request.urlopen(result.pdf_url, context=ssl_context) as response:
                    filename.write_bytes(response.read())

                # 히스토리 엔트리 생성 및 저장
                entry = {
                    "arxiv_id": arxiv_id,
                    "title": result.title,
                    "authors": [author.name for author in result.authors],
                    "downloaded_at": datetime.now().isoformat(),
                    "source": "arXiv",
                    "pdf_url": result.pdf_url
                }
                self._save_download_history(entry)
                self.download_history.append(entry)
                downloaded += 1

                # 오픈소스 추출
                github_links = self._extract_github_links(filename)
                if github_links:
                    os_entry = {
                        "arxiv_id": arxiv_id,
                        "title": result.title,
                        "github_links": github_links,
                        "updated_at": datetime.now().isoformat()
                    }
                    self._save_open_source_info(os_entry)

                print(f"다운로드 완료: {result.title}")

            except Exception as e:
                print(f"다운로드 실패 ({arxiv_id}): {e}")

        print(f"총 {downloaded}개 새 논문 다운로드 완료")
        return downloaded

    def scan_user_added_papers(self) -> int:
        """사용자가 직접 추가한 논문 감지 → 히스토리에 반영"""
        added = 0
        current_ids = {entry["arxiv_id"] for entry in self.download_history if isinstance(entry, dict) and "arxiv_id" in entry}

        for file in self.paper_dir.iterdir():
            if file.suffix.lower() == ".pdf":
                arxiv_id = file.stem
                if arxiv_id not in current_ids:
                    entry = {
                        "arxiv_id": arxiv_id,
                        "title": "사용자 직접 추가",
                        "authors": [],
                        "downloaded_at": datetime.now().isoformat(),
                        "source": "user_added",
                        "pdf_url": ""
                    }
                    self._save_download_history(entry)
                    self.download_history.append(entry)
                    added += 1
                    print(f"사용자 추가 논문 감지: {file.name}")
        return added

    def get_open_source_list(self) -> List[Dict]:
        """저장된 오픈소스 정보 로드"""
        results = []
        if self.open_source_path.exists():
            with open(self.open_source_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        results.append(json.loads(line))
        return results


# Prefect Task
try:
    from prefect import task

    @task(name="Download New Papers")
    def download_task(query: Optional[str] = None):
        manager = PaperManager()
        return manager.download_from_arxiv(query=query)

    @task(name="Scan User Added Papers")
    def scan_task():
        manager = PaperManager()
        return manager.scan_user_added_papers()

except ImportError:
    print("Prefect 미설치 - 로컬 테스트만 가능")


# __main__ 테스트
if __name__ == "__main__":
    print("=== Paper Manager 테스트 시작 ===")
    manager = PaperManager()

    print("사용자 추가 논문 스캔...")
    manager.scan_user_added_papers()

    print("\narXiv에서 5개 논문 다운로드 테스트...")
    manager.download_from_arxiv(max_results=5)

    print("\n현재 저장된 오픈소스 프로젝트:")
    for item in manager.get_open_source_list():
        print(f"- {item.get('title', '제목 없음')}")
        for link in item.get('github_links', []):
            print(f"  → {link}")

    print("\n테스트 완료!")