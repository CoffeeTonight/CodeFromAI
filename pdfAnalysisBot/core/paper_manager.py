# core/paper_manager.py
import os
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import arxiv
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from core.config import Config

# SSL 경고 무시 및 안정적인 세션 설정
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.verify = False


class PaperManager:
    def __init__(self):
        self.paper_dir = Config.PAPER_DIR
        self.history_path = Config.DOWNLOAD_HISTORY_PATH
        self.open_source_path = Config.OPEN_SOURCE_DB_PATH
        self.download_history = self._load_download_history()

    def _load_download_history(self) -> List[Dict]:
        history = []
        if not self.history_path.exists():
            return history

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
                    print(f"[경고] JSON 파싱 실패 (라인 {line_num}): {e}")
        return history

    def _save_download_history(self, entry: Dict):
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
        with open(self.open_source_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _extract_title_from_pdf(self, pdf_path: Path) -> Optional[str]:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            first_page_text = doc[0].get_text()
            doc.close()

            lines = [line.strip() for line in first_page_text.split("\n") if line.strip()]
            for line in lines[:15]:
                if len(line) > 20 and (line.isupper() or line.endswith((".", ":", "?")) or "Abstract" in line):
                    return line
            return lines[0] if lines else None
        except Exception as e:
            print(f"제목 추출 실패 ({pdf_path.name}): {e}")
            return None

        def download_from_arxiv(self, query: Optional[str] = None, max_results: Optional[int] = None, target_count: Optional[int] = None) -> int:
        max_results = max_results or Config.ARXIV_MAX_RESULTS
        query = query or Config.DEFAULT_ARXIV_QUERY

        current_count = len(list(self.paper_dir.glob("*.pdf")))
        print(f"현재 PDF 수: {current_count}개")

        if target_count is not None:
            needed = max(0, target_count - current_count)
            if needed == 0:
                print(f"목표 {target_count}개 달성 → 다운로드 스킵")
                return 0
            max_results = max(max_results, needed)
            print(f"목표 {target_count}개 → 최대 {max_results}개 검색")

        # 정렬 기준
        sort_by_map = {
            "submitted_date": "submittedDate",
            "last_updated_date": "lastUpdatedDate",
            "relevance": "relevance"
        }
        sort_order_map = {
            "ascending": "ascending",
            "descending": "descending"
        }
        sort_by = sort_by_map.get(Config.ARXIV_SORT_BY, "relevance")
        sort_order = sort_order_map.get(Config.ARXIV_SORT_ORDER, "descending")

        print(f"arXiv 정렬: {Config.ARXIV_SORT_BY} ({Config.ARXIV_SORT_ORDER})")
        print(f"arXiv 다운로드 방식: {'명시적 RSS (회사 추천)' if not Config.ARXIV_USE_LIB else 'arxiv 라이브러리'}")

        downloaded = 0
        current_llm = Config.SELECTED_MODEL

        if Config.ARXIV_USE_LIB:
            # arXiv 라이브러리 방식
            sort_criterion_map = {
                "submitted_date": arxiv.SortCriterion.SubmittedDate,
                "last_updated_date": arxiv.SortCriterion.LastUpdatedDate,
                "relevance": arxiv.SortCriterion.Relevance
            }
            sort_order_criterion_map = {
                "ascending": arxiv.SortOrder.Ascending,
                "descending": arxiv.SortOrder.Descending
            }
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=sort_criterion_map.get(Config.ARXIV_SORT_BY, arxiv.SortCriterion.Relevance),
                sort_order=sort_order_criterion_map.get(Config.ARXIV_SORT_ORDER, arxiv.SortOrder.Descending)
            )
            client = arxiv.Client()
            results = client.results(search)
        else:
            # 명시적 RSS 방식 (회사에서 잘 됨)
            encoded_query = requests.utils.quote(query)
            rss_url = (
                f"https://export.arxiv.org/api/query?"
                f"search_query={encoded_query}"
                f"&start=0&max_results={max_results}"
                f"&sortBy={sort_by}&sortOrder={sort_order}"
            )
            print(f"RSS URL: {rss_url}")

            try:
                response = session.get(rss_url, timeout=120)
                response.raise_for_status()
            except Exception as e:
                print(f"RSS 요청 실패: {e}")
                return 0

            feed = feedparser.parse(response.content)
            if feed.bozo:
                print(f"피드 파싱 오류: {feed.bozo_exception}")
                return 0

            results = feed.entries

        for result in results:
            if Config.ARXIV_USE_LIB:
                arxiv_id = result.entry_id.split('/')[-1].split('v')[0]  # 버전 제거
                title = result.title
                authors = [a.name for a in result.authors]
                pdf_url = result.pdf_url
            else:
                arxiv_id = result.id.split('/')[-1].split('v')[0]
                title = result.title
                authors = [a.get('name', '') for a in result.get('authors', [])]
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            versioned_id = arxiv_id

            if any(e.get("arxiv_id") == versioned_id for e in self.download_history):
                continue

            filename = self.paper_dir / f"{versioned_id}.pdf"

            try:
                print(f"다운로드 시도: {title} ({versioned_id})")
                response = session.get(pdf_url, timeout=120)
                response.raise_for_status()
                filename.write_bytes(response.content)
                print(f"다운로드 완료: {title}")

                entry = {
                    "arxiv_id": versioned_id,
                    "title": title,
                    "authors": authors,
                    "downloaded_at": datetime.now().isoformat(),
                    "source": "arXiv",
                    "pdf_url": pdf_url,
                    "processed_with_llm": current_llm,
                    "processed_at": datetime.now().isoformat()
                }
                self._save_download_history(entry)
                self.download_history.append(entry)
                downloaded += 1

                github_links = self._extract_github_links(filename)
                if github_links:
                    os_entry = {
                        "arxiv_id": versioned_id,
                        "title": title,
                        "github_links": github_links,
                        "detected_at": datetime.now().isoformat(),
                        "detected_with_llm": current_llm,
                        "note": "GitHub 링크 자동 추출"
                    }
                    self._save_open_source_info(os_entry)
                    print(f"  → 오픈소스 발견: {len(github_links)}개 링크")

            except Exception as e:
                print(f"다운로드 실패 ({versioned_id}): {e}")

        print(f"총 {downloaded}개 새 논문 다운로드 완료 (LLM: {current_llm})")
        return downloaded

    def scan_user_added_papers(self) -> int:
        added = 0
        current_ids = {e.get("arxiv_id") for e in self.download_history if e.get("arxiv_id")}
        current_llm = Config.SELECTED_MODEL

        for file in self.paper_dir.iterdir():
            if file.suffix.lower() != ".pdf":
                continue
            arxiv_id = file.stem
            if arxiv_id not in current_ids:
                title = self._extract_title_from_pdf(file) or "사용자 직접 추가 (제목 자동 추출 실패)"
                entry = {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "authors": [],
                    "downloaded_at": datetime.now().isoformat(),
                    "source": "user_added",
                    "pdf_url": "",
                    "processed_with_llm": current_llm,
                    "note": "사용자 수동 추가 논문 감지"
                }
                self._save_download_history(entry)
                self.download_history.append(entry)
                current_ids.add(arxiv_id)
                added += 1
                print(f"사용자 추가 논문 감지: {file.name} → 제목: {title}")

        if added > 0:
            print(f"{added}개 사용자 추가 논문 등록 완료 (LLM: {current_llm})")
        return added

    def verify_and_cleanup_history(self, mode: str = "auto") -> Dict[str, int]:
        """paper 폴더와 히스토리 동기화 (의도적 삭제 존중)"""
        if not self.paper_dir.exists():
            self.paper_dir.mkdir(parents=True, exist_ok=True)
            return {"missing": 0, "cleaned": 0, "redownloaded": 0}

        existing_pdfs = {f.stem for f in self.paper_dir.iterdir() if f.suffix.lower() == ".pdf"}
        missing_entries = []
        valid_entries = []

        print(f"히스토리 기록: {len(self.download_history)}개")
        print(f"실제 PDF 파일: {len(existing_pdfs)}개")

        for entry in self.download_history:
            aid = entry.get("arxiv_id")
            if aid and aid in existing_pdfs:
                valid_entries.append(entry)
            elif aid:
                missing_entries.append(entry)

        if not missing_entries:
            print("모든 논문 PDF가 정상 존재합니다.")
            return {"missing": 0, "cleaned": 0, "redownloaded": 0}

        print(f"\n{len(missing_entries)}개 PDF가 존재하지 않습니다.")

        cleaned = 0
        redownloaded = 0

        if mode == "auto":
            print("→ mode='auto': 누락 보고만 하고 아무 작업 안 함 (의도적 삭제 존중)")

        elif mode == "cleanup":
            print("→ mode='cleanup': 누락 엔트리 히스토리에서 삭제")
            backup = self.history_path.with_suffix(".jsonl.backup")
            shutil.copy(self.history_path, backup)
            print(f"백업: {backup}")
            with open(self.history_path, "w", encoding="utf-8") as f:
                for e in valid_entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            self.download_history = valid_entries
            cleaned = len(missing_entries)

        elif mode == "redownload":
            print("→ mode='redownload': 누락된 arXiv 논문 자동 재다운로드")
            redownloaded = self.redownload_missing_papers()

        elif mode == "interactive":
            print("→ mode='interactive': 수동 선택")
            for entry in missing_entries:
                title = entry.get("title", "제목 없음")
                aid = entry.get("arxiv_id")
                src = entry.get("source")
                ans = input(f"[누락] {aid} | {title} ({src})\n  [k]eep / [d]elete / [r]edownload ? (k/d/r): ").lower()
                if ans == "d":
                    cleaned += 1
                elif ans == "r" and src == "arXiv":
                    if self._redownload_single(entry):
                        redownloaded += 1

            if cleaned > 0:
                valid_entries = [e for e in self.download_history if e.get("arxiv_id") not in {m.get("arxiv_id") for m in missing_entries if ans == "d"}]
                self._rewrite_history(valid_entries)

        return {"missing": len(missing_entries), "cleaned": cleaned, "redownloaded": redownloaded}

    def _redownload_single(self, entry: Dict) -> bool:
        pdf_url = entry.get("pdf_url")
        aid = entry.get("arxiv_id")
        if not pdf_url or not aid:
            return False
        filename = self.paper_dir / f"{aid}.pdf"
        try:
            resp = session.get(pdf_url, timeout=120)
            resp.raise_for_status()
            filename.write_bytes(resp.content)
            print(f"재다운로드 성공: {aid}")
            return True
        except Exception as e:
            print(f"재다운로드 실패 {aid}: {e}")
            return False

    def redownload_missing_papers(self, max_results: Optional[int] = None) -> int:
        redownloaded = 0
        existing = {f.stem for f in self.paper_dir.iterdir() if f.suffix.lower() == ".pdf"}
        for entry in self.download_history:
            aid = entry.get("arxiv_id")
            if aid and aid not in existing and entry.get("source") == "arXiv":
                if self._redownload_single(entry):
                    redownloaded += 1
                if max_results and redownloaded >= max_results:
                    break
        return redownloaded

    def _rewrite_history(self, entries: List[Dict]):
        backup = self.history_path.with_suffix(".jsonl.backup")
        shutil.copy(self.history_path, backup)
        with open(self.history_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        self.download_history = entries

    def generate_current_papers_snapshot(self) -> int:
        """현재 paper 폴더의 모든 PDF를 스캔해 current_papers.jsonl 생성"""
        snapshot_path = Config.DB_DIR / "current_papers.jsonl"
        entries = []

        print("current_papers.jsonl 스냅샷 생성 중...")

        for pdf_file in self.paper_dir.iterdir():
            if pdf_file.suffix.lower() != ".pdf":
                continue
            aid = pdf_file.stem

            hist_entry = next((e for e in self.download_history if e.get("arxiv_id") == aid), None)
            if hist_entry:
                entry = {
                    "arxiv_id": aid,
                    "title": hist_entry.get("title", "제목 없음"),
                    "authors": hist_entry.get("authors", []),
                    "source": hist_entry.get("source", "unknown"),
                    "added_at": hist_entry.get("downloaded_at", "unknown"),
                    "has_github": bool(self._extract_github_links(pdf_file)),
                    "file_exists": True
                }
            else:
                title = self._extract_title_from_pdf(pdf_file) or "제목 자동 추출 실패"
                entry = {
                    "arxiv_id": aid,
                    "title": title,
                    "authors": [],
                    "source": "user_added",
                    "added_at": datetime.now().isoformat(),
                    "has_github": bool(self._extract_github_links(pdf_file)),
                    "file_exists": True,
                    "notes": "사용자 직접 추가"
                }
            entries.append(entry)

        with open(snapshot_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

        print(f"current_papers.jsonl 생성 완료: {len(entries)}개 논문")
        return len(entries)

    def get_open_source_list(self) -> List[Dict]:
        results = []
        if self.open_source_path.exists():
            with open(self.open_source_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            results.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return results


# Prefect 호환 (옵션)
try:
    from prefect import task

    @task(name="Download New Papers")
    def download_task(query: Optional[str] = None, max_results: int = 20):
        manager = PaperManager()
        return manager.download_from_arxiv(query=query, max_results=max_results)

    @task(name="Scan User Added Papers")
    def scan_task():
        manager = PaperManager()
        return manager.scan_user_added_papers()

except ImportError:
    pass


# 테스트
if __name__ == "__main__":
    print("=== Paper Manager 최종 테스트 ===")
    print(f"현재 LLM: {Config.SELECTED_MODEL}")
    manager = PaperManager()

    manager.verify_and_cleanup_history(mode="auto")
    manager.scan_user_added_papers()
    manager.download_from_arxiv(max_results=5)
    manager.generate_current_papers_snapshot()

    print("\n현재 오픈소스:")
    for item in manager.get_open_source_list():
        print(f"- {item.get('title')} (LLM: {item.get('detected_with_llm')})")
        for link in item.get("github_links", []):
            print(f"  → {link}")

    print("\n테스트 완료!")
