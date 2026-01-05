# core/paper_manager.py
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import feedparser
import urllib.request
import ssl
from config import Config

class PaperManager:
    def __init__(self):
        self.paper_dir = Config.PAPER_DIR
        self.history_path = Config.DOWNLOAD_HISTORY_PATH
        self.open_source_path = Config.OPEN_SOURCE_DB_PATH
        self.download_history = self._load_download_history()

        if not self.download_history:
            self.download_history = []

    def _load_download_history(self) -> List[Dict]:
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
                        except json.JSONDecodeError as e:
                            print(f"손상된 줄 무시 (line {line_num}): {e}")
            except Exception as e:
                print(f"히스토리 파일 읽기 실패: {e}")
        else:
            print("다운로드 히스토리 파일 없음 - 새로 생성됩니다.")
        return history

    def _save_download_history(self, entry: Dict):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _extract_github_links(self, pdf_path: Path) -> List[str]:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()

            pattern = r'https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'
            links = re.findall(pattern, text)
            return list(set(links))
        except Exception as e:
            print(f"GitHub 추출 실패 ({pdf_path.name}): {e}")
            return []

    def _save_open_source_info(self, entry: Dict):
        self.open_source_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.open_source_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def download_from_arxiv_rss(self, category: str = "cs", query: Optional[str] = None, max_results: int = 30) -> int:
        """arXiv RSS 피드로 논문 다운로드 (키워드 검색 + SSL 우회)"""
        # SSL 우회 컨텍스트 전역 생성
        ssl_context = ssl._create_unverified_context()

        if query and query.strip():
            # 정확한 키워드 검색 RSS URL 생성
            query_encoded = urllib.parse.quote(query.strip())
            rss_url = f"https://export.arxiv.org/api/query?search_query={query_encoded}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
            print(f"[RSS] 키워드 검색 사용: {query.strip()}")
        else:
            rss_url = f"https://arxiv.org/rss/{category}"
            print(f"[RSS] 카테고리 사용: {category}")

        print(f"[RSS] 피드 URL: {rss_url}")

        try:
            with urllib.request.urlopen(rss_url, context=ssl_context) as response:
                feed_data = response.read()
            feed = feedparser.parse(feed_data)
        except Exception as e:
            print(f"[오류] RSS 피드 접속 실패: {e}")
            return 0

        if feed.bozo:
            print(f"[오류] RSS 파싱 오류: {feed.get('bozo_exception', 'Unknown')}")
            return 0

        entries = feed.entries
        print(f"[성공] {len(entries)}개 논문 발견")

        downloaded = 0

        for entry in entries:
            try:
                # arXiv ID 추출
                if query:
                    # API 방식에서 ID 추출
                    arxiv_id = entry.id.split('/abs/')[-1].split('v')[0]
                else:
                    # RSS 방식에서 ID 추출
                    arxiv_id = entry.link.split('/')[-1]

                # 중복 체크
                if any(e.get("arxiv_id") == arxiv_id for e in self.download_history):
                    continue

                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                filename = self.paper_dir / f"{arxiv_id}.pdf"

                # PDF 다운로드
                with urllib.request.urlopen(pdf_url, context=ssl_context) as response:
                    filename.write_bytes(response.read())

                # 메타데이터 추출
                title = entry.get("title", "제목 없음")
                authors = []
                if "author" in entry:
                    if isinstance(entry.author, list):
                        authors = [a.get("name", "") for a in entry.author]
                    else:
                        authors = [entry.author.get("name", "")] if isinstance(entry.author, dict) else [str(entry.author)]

                entry_data = {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "authors": authors,
                    "downloaded_at": datetime.now().isoformat(),
                    "source": "arXiv_RSS",
                    "pdf_url": pdf_url
                }
                self._save_download_history(entry_data)
                self.download_history.append(entry_data)

                # 오픈소스 추출
                github_links = self._extract_github_links(filename)
                if github_links:
                    os_entry = {
                        "arxiv_id": arxiv_id,
                        "title": title,
                        "github_links": github_links,
                        "updated_at": datetime.now().isoformat()
                    }
                    self._save_open_source_info(os_entry)

                print(f"[다운로드 완료] {title}")
                downloaded += 1

            except Exception as e:
                print(f"[다운로드 실패] {arxiv_id}: {e}")

        print(f"[완료] 총 {downloaded}개 새 논문 다운로드")
        return downloaded

    def scan_user_added_papers(self) -> int:
        added = 0
        current_ids = {e.get("arxiv_id") for e in self.download_history if e.get("arxiv_id")}

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
        results = []
        if self.open_source_path.exists():
            with open(self.open_source_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        results.append(json.loads(line))
        return results

# __main__ 테스트
if __name__ == "__main__":
    print("=== Paper Manager 테스트 시작 ===")
    manager = PaperManager()

    print("사용자 추가 논문 스캔...")
    manager.scan_user_added_papers()

    print("\narXiv에서 논문 다운로드 테스트...")
    # 기본 키워드 사용
    manager.download_from_arxiv_rss(query=Config.DEFAULT_ARXIV_QUERY, max_results=10)

    print("\n현재 저장된 오픈소스 프로젝트:")
    for item in manager.get_open_source_list():
        print(f"- {item.get('title', '제목 없음')}")
        for link in item.get('github_links', []):
            print(f"  → {link}")

    print("\n테스트 완료!")