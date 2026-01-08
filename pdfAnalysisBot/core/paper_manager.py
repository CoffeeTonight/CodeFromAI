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
import feedparser

from core.config import Config
from core.utils import get_logger  # 중앙 로거

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()
retry_strategy = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["HEAD", "GET"])
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.verify = False

logger = get_logger("PaperManager")

class PaperManager:
    def __init__(self):
        # 서브폴더 경로
        self.arxiv_paper_dir = Config.ARXIV_PAPER_DIR
        self.semantic_paper_dir = Config.SEMANTIC_PAPER_DIR
        self.conference_paper_dir = Config.CONFERENCE_PAPER_DIR
        self.user_paper_dir = Config.USER_PAPER_DIR

        self.arxiv_data_dir = Config.ARXIV_DATA_DIR
        self.semantic_data_dir = Config.SEMANTIC_DATA_DIR
        self.conference_data_dir = Config.CONFERENCE_DATA_DIR
        self.user_data_dir = Config.USER_DATA_DIR

        self.history_path = Config.DOWNLOAD_HISTORY_PATH
        self.open_source_path = Config.OPEN_SOURCE_DB_PATH
        self.download_history = self._load_download_history()

    def _load_download_history(self) -> List[Dict]:
        history = []
        if not self.history_path.exists():
            logger.info("다운로드 히스토리 파일 없음 → 빈 리스트 반환")
            return history
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
                        logger.warning(f"JSON 파싱 실패 (라인 {line_num}): {e}")
        except Exception as e:
            logger.error(f"다운로드 히스토리 로드 실패: {e}")
        logger.info(f"다운로드 히스토리 로드 완료: {len(history)}개")
        return history

    def _save_download_history(self, entry: Dict):
        try:
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.debug(f"히스토리 저장: {entry.get('title', entry.get('arxiv_id', 'unknown'))}")
        except Exception as e:
            logger.error(f"히스토리 저장 실패: {e}")

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
            unique_links = list(set(links))
            if unique_links:
                logger.info(f"GitHub 링크 발견 ({pdf_path.name}): {len(unique_links)}개")
            return unique_links
        except Exception as e:
            logger.warning(f"GitHub 추출 실패 ({pdf_path.name}): {e}")
            return []

    def _save_open_source_info(self, entry: Dict):
        try:
            with open(self.open_source_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.info(f"오픈소스 정보 저장: {entry.get('title')}")
        except Exception as e:
            logger.error(f"오픈소스 정보 저장 실패: {e}")

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
            logger.warning(f"제목 추출 실패 ({pdf_path.name}): {e}")
            return None

    def download_from_arxiv(self, query: Optional[str] = None, max_results: Optional[int] = None, target_count: Optional[int] = None) -> int:
        max_results = max_results or Config.ARXIV_MAX_RESULTS
        query = query or Config.DEFAULT_ARXIV_QUERY
        logger.info(f"다운로드 점수 기준: 최신성 기반 (1년 decay) + 정렬: {Config.ARXIV_SORT_BY}")

        current_count = len(list(self.arxiv_paper_dir.glob("*.pdf")))
        logger.info(f"arXiv PDF 현재 수: {current_count}개")

        if target_count is not None:
            needed = max(0, target_count - current_count)
            if needed == 0:
                logger.info(f"목표 {target_count}개 달성 → 다운로드 스킵")
                return 0
            max_results = max(max_results, needed)
            logger.info(f"목표 {target_count}개 → 최대 {max_results}개 검색")

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

        logger.info(f"arXiv 정렬: {Config.ARXIV_SORT_BY} ({Config.ARXIV_SORT_ORDER})")
        logger.info(f"arXiv 다운로드 방식: {'명시적 RSS URL' if not Config.ARXIV_USE_LIB else 'arxiv 라이브러리'}")

        downloaded = 0
        current_llm = Config.SELECTED_MODEL

        if Config.ARXIV_USE_LIB:
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
            encoded_query = requests.utils.quote(query)
            rss_url = (
                f"https://export.arxiv.org/api/query?"
                f"search_query={encoded_query}"
                f"&start=0&max_results={max_results}"
                f"&sortBy={sort_by}&sortOrder={sort_order}"
            )
            logger.info(f"RSS URL: {rss_url}")

            try:
                response = session.get(rss_url, timeout=120)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"RSS 요청 실패: {e}")
                return 0

            feed = feedparser.parse(response.content)
            if feed.bozo:
                logger.error(f"피드 파싱 오류: {feed.bozo_exception}")
                return 0

            results = feed.entries

        for result in results:
            if Config.ARXIV_USE_LIB:
                arxiv_id = result.entry_id.split('/')[-1].split('v')[0]
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

            filename = self.arxiv_paper_dir / f"{versioned_id}.pdf"

            try:
                logger.info(f"다운로드 시도: {title} ({versioned_id})")
                response = session.get(pdf_url, timeout=120)
                response.raise_for_status()
                filename.write_bytes(response.content)
                logger.info(f"다운로드 완료: {title}")

                # 점수 계산 및 출력 추가 (핵심!!!)
                try:
                    # published 날짜 추출 (RSS와 라이브러리 방식 통합)
                    published_str = result.published.replace("Z", "+00:00")
                    published_date = datetime.fromisoformat(published_str)
                except:
                    published_date = datetime.now()  # 파싱 실패 시 현재 날짜

                days_old = (datetime.now() - published_date).days
                latest_score = max(0, 100 - days_old / 3.65)  # 대략 1년 decay
                rank = downloaded + 1

                # 실시간 점수 출력
                logger.info(f"  → 순위 {rank}위 | 점수 {latest_score:.1f} | 기준: {Config.ARXIV_SORT_BY} | {title}")

                entry = {
                    "arxiv_id": versioned_id,
                    "title": title,
                    "authors": authors,
                    "downloaded_at": datetime.now().isoformat(),
                    "source": "arXiv",
                    "folder": "arxiv",
                    "download_reason": "target_count_needed" if target_count else "max_results",
                    "download_rank": rank,
                    "download_score": round(latest_score, 1),
                    "download_criteria": f"{Config.ARXIV_SORT_BY} ({Config.ARXIV_SORT_ORDER})"
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
                    logger.info(f"  → 오픈소스 발견: {len(github_links)}개 링크")

            except Exception as e:
                logger.error(f"다운로드 실패 ({versioned_id}): {e}")

        logger.info(f"총 {downloaded}개 새 논문 다운로드 완료 (LLM: {current_llm})")
        return downloaded

    def scan_user_added_papers(self) -> int:
        added = 0
        current_ids = {e.get("arxiv_id") for e in self.download_history if e.get("arxiv_id")}
        current_llm = Config.SELECTED_MODEL

        for dir_path in [self.user_paper_dir, self.conference_paper_dir, self.semantic_paper_dir]:
            if not dir_path.exists():
                continue
            for file in dir_path.iterdir():
                if file.suffix.lower() != ".pdf":
                    continue
                arxiv_id = file.stem
                if arxiv_id not in current_ids:
                    title = self._extract_title_from_pdf(file) or "사용자 추가 논문"
                    folder_name = dir_path.name
                    entry = {
                        "arxiv_id": arxiv_id,
                        "title": title,
                        "authors": [],
                        "downloaded_at": datetime.now().isoformat(),
                        "source": "user_added",
                        "folder": folder_name,
                        "note": f"{folder_name} 폴더에서 감지"
                    }
                    self._save_download_history(entry)
                    self.download_history.append(entry)
                    current_ids.add(arxiv_id)
                    added += 1
                    logger.info(f"{folder_name} 폴더 논문 감지: {file.name}")

        if added > 0:
            logger.info(f"{added}개 사용자 추가 논문 등록 완료")
        return added

    def verify_and_cleanup_history(self, mode: str = "auto") -> Dict[str, int]:
        all_paper_dirs = [
            Config.ARXIV_PAPER_DIR,
            Config.SEMANTIC_PAPER_DIR,
            Config.CONFERENCE_PAPER_DIR,
            Config.USER_PAPER_DIR
        ]

        existing_pdfs = set()
        for dir_path in all_paper_dirs:
            if dir_path.exists():
                existing_pdfs.update({f.stem for f in dir_path.iterdir() if f.suffix.lower() == ".pdf"})

        missing_entries = []
        valid_entries = []

        logger.info(f"히스토리 기록: {len(self.download_history)}개")
        logger.info(f"실제 PDF 파일 (모든 폴더): {len(existing_pdfs)}개")

        for entry in self.download_history:
            aid = entry.get("arxiv_id")
            if aid and aid in existing_pdfs:
                valid_entries.append(entry)
            elif aid:
                missing_entries.append(entry)

        if not missing_entries:
            logger.info("모든 논문 PDF가 정상 존재합니다.")
            return {"missing": 0, "cleaned": 0, "redownloaded": 0}

        logger.info(f"\n{len(missing_entries)}개 PDF가 존재하지 않습니다.")

        cleaned = 0
        redownloaded = 0

        if mode == "auto":
            logger.info("→ mode='auto': 누락 보고만 하고 아무 작업 안 함 (의도적 삭제 존중)")

        elif mode == "cleanup":
            logger.info("→ mode='cleanup': 누락 엔트리 히스토리에서 삭제")
            backup = self.history_path.with_suffix(".jsonl.backup")
            shutil.copy(self.history_path, backup)
            logger.info(f"백업: {backup}")
            with open(self.history_path, "w", encoding="utf-8") as f:
                for e in valid_entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            self.download_history = valid_entries
            cleaned = len(missing_entries)

        elif mode == "redownload":
            logger.info("→ mode='redownload': 누락된 arXiv 논문 자동 재다운로드")
            redownloaded = self.redownload_missing_papers()

        return {"missing": len(missing_entries), "cleaned": cleaned, "redownloaded": redownloaded}

    def _redownload_single(self, entry: Dict) -> bool:
        pdf_url = entry.get("pdf_url")
        aid = entry.get("arxiv_id")
        if not pdf_url or not aid:
            return False
        # arXiv 폴더에 저장 (arXiv 우선)
        filename = self.arxiv_paper_dir / f"{aid}.pdf"
        try:
            resp = session.get(pdf_url, timeout=120)
            resp.raise_for_status()
            filename.write_bytes(resp.content)
            logger.info(f"재다운로드 성공: {aid}")
            return True
        except Exception as e:
            logger.error(f"재다운로드 실패 {aid}: {e}")
            return False

    def redownload_missing_papers(self, max_results: Optional[int] = None) -> int:
        redownloaded = 0
        all_existing = set()
        for dir_path in [Config.ARXIV_PAPER_DIR, Config.SEMANTIC_PAPER_DIR, Config.CONFERENCE_PAPER_DIR, Config.USER_PAPER_DIR]:
            if dir_path.exists():
                all_existing.update({f.stem for f in dir_path.iterdir() if f.suffix.lower() == ".pdf"})

        for entry in self.download_history:
            aid = entry.get("arxiv_id")
            if aid and aid not in all_existing and entry.get("source") == "arXiv":
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
        snapshot_path = Config.DB_DIR / "current_papers.jsonl"
        entries = []

        logger.info("current_papers.jsonl 스냅샷 생성 중...")

        all_paper_dirs = [
            Config.ARXIV_PAPER_DIR,
            Config.SEMANTIC_PAPER_DIR,
            Config.CONFERENCE_PAPER_DIR,
            Config.USER_PAPER_DIR
        ]

        for dir_path in all_paper_dirs:
            if not dir_path.exists():
                continue
            for pdf_file in dir_path.iterdir():
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
                        "folder": dir_path.name,
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
                        "folder": dir_path.name,
                        "added_at": datetime.now().isoformat(),
                        "has_github": bool(self._extract_github_links(pdf_file)),
                        "file_exists": True,
                        "notes": "사용자 직접 추가"
                    }
                entries.append(entry)

        with open(snapshot_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

        logger.info(f"current_papers.jsonl 생성 완료: {len(entries)}개 논문")
        return len(entries)

    def get_open_source_list(self) -> List[Dict]:
        results = []
        if self.open_source_path.exists():
            try:
                with open(self.open_source_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                results.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                logger.error(f"오픈소스 목록 로드 실패: {e}")
        logger.debug(f"오픈소스 목록 반환: {len(results)}개")
        return results

    def download_from_arxiv_mixed_sort(
        self,
        query: Optional[str] = None,
        max_results: int = 30,
        target_count: Optional[int] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> int:
        """
        arXiv에서 혼합 정렬 (submitted_date, relevance 등)로 다운로드
        weights 예시: {"submitted_date": 0.6, "relevance": 0.4}
        """
        query = query or Config.DEFAULT_ARXIV_QUERY
        weights = weights or {"submitted_date": 0.7, "relevance": 0.3}

        current_count = len(list(self.arxiv_paper_dir.glob("*.pdf")))
        logger.info(f"[arXiv] 현재 PDF 수: {current_count}개")

        if target_count is not None:
            needed = max(0, target_count - current_count)
            if needed == 0:
                logger.info(f"[arXiv] 목표 {target_count}개 달성 → 다운로드 스킵")
                return 0
            per_sort_results = max(20, needed * 3)
        else:
            per_sort_results = max_results

        sort_mapping = {
            "submitted_date": arxiv.SortCriterion.SubmittedDate,
            "last_updated_date": arxiv.SortCriterion.LastUpdatedDate,
            "relevance": arxiv.SortCriterion.Relevance
        }

        all_results = {}
        for criterion, weight in weights.items():
            if weight <= 0:
                continue
            sort_criterion = sort_mapping.get(criterion, arxiv.SortCriterion.Relevance)
            sort_order = arxiv.SortOrder.Descending

            if Config.ARXIV_USE_LIB:
                search = arxiv.Search(
                    query=query,
                    max_results=per_sort_results,
                    sort_by=sort_criterion,
                    sort_order=sort_order
                )
                client = arxiv.Client()
                results = list(client.results(search))
            else:
                encoded_query = requests.utils.quote(query)
                sort_by = criterion if criterion != "submitted_date" else "submittedDate"
                sort_by = sort_by if sort_by != "last_updated_date" else "lastUpdatedDate"
                rss_url = (
                    f"https://export.arxiv.org/api/query?"
                    f"search_query={encoded_query}"
                    f"&start=0&max_results={per_sort_results}"
                    f"&sortBy={sort_by}&sortOrder=descending"
                )
                logger.debug(f"[arXiv] RSS URL: {rss_url}")

                try:
                    resp = session.get(rss_url, timeout=30)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"[arXiv] RSS 요청 실패: {e}")
                    results = []
                else:
                    feed = feedparser.parse(resp.content)
                    if feed.bozo:
                        logger.error(f"[arXiv] 피드 파싱 오류: {feed.bozo_exception}")
                        results = []
                    else:
                        results = feed.entries

            all_results[criterion] = results
            logger.info(f"[arXiv] {criterion} 기준 검색 완료: {len(results)}개")

        # 점수 계산
        paper_scores = {}
        for criterion, papers in all_results.items():
            weight = weights[criterion]
            for rank, result in enumerate(papers, 1):
                if Config.ARXIV_USE_LIB:
                    arxiv_id = result.entry_id.split('/')[-1].split('v')[0]
                else:
                    arxiv_id = result.id.split('/')[-1].split('v')[0]

                rank_score = 100 * (1 - (rank - 1) / max(len(papers), 1))
                weighted_score = rank_score * weight

                if arxiv_id not in paper_scores:
                    paper_scores[arxiv_id] = {"result": result, "score": 0.0}
                paper_scores[arxiv_id]["score"] += weighted_score

        sorted_papers = sorted(paper_scores.items(), key=lambda x: x[1]["score"], reverse=True)

        download_limit = target_count or max_results
        downloaded = 0
        current_llm = Config.SELECTED_MODEL

        for rank, (arxiv_id, info) in enumerate(sorted_papers[:download_limit], 1):
            result = info["result"]
            title = result.title if Config.ARXIV_USE_LIB else result.title
            pdf_url = result.pdf_url if Config.ARXIV_USE_LIB else f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            if any(e.get("arxiv_id") == arxiv_id for e in self.download_history):
                continue

            filename = self.arxiv_paper_dir / f"{arxiv_id}.pdf"

            try:
                logger.info(f"[arXiv] 다운로드 시도 ({info['score']:.1f}점, 순위 {rank}위): {title}")
                resp = session.get(pdf_url, timeout=120)
                resp.raise_for_status()
                filename.write_bytes(resp.content)
                logger.info(f"[arXiv] 다운로드 완료: {title}")

                entry = {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "authors": [],
                    "downloaded_at": datetime.now().isoformat(),
                    "source": "arXiv",
                    "folder": "arxiv",
                    "download_reason": "mixed_sort",
                    "download_rank": rank,
                    "download_score": round(info["score"], 2),
                    "download_criteria": f"mixed: {weights}"
                }
                self._save_download_history(entry)
                self.download_history.append(entry)
                downloaded += 1

                github_links = self._extract_github_links(filename)
                if github_links:
                    os_entry = {
                        "arxiv_id": arxiv_id,
                        "title": title,
                        "github_links": github_links,
                        "detected_at": datetime.now().isoformat(),
                        "detected_with_llm": current_llm,
                        "note": "GitHub 링크 자동 추출"
                    }
                    self._save_open_source_info(os_entry)

            except Exception as e:
                logger.error(f"[arXiv] 다운로드 실패: {e}")

        logger.info(f"[arXiv] 총 {downloaded}개 논문 다운로드 완료 (혼합 정렬)")
        return downloaded

    def download_from_semantic_scholar_mixed_sort(
        self,
        query: Optional[str] = None,
        max_results: int = 30,
        target_count: Optional[int] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> int:
        """
        Semantic Scholar에서 혼합 정렬(citation + relevance + latest)로 논문 다운로드
        weights 예시: {"citation": 0.6, "relevance": 0.3, "latest": 0.1}
        """
        query = query or Config.DEFAULT_ARXIV_QUERY
        weights = weights or {"citation": 0.6, "relevance": 0.3, "latest": 0.1}

        current_count = len(list(self.semantic_paper_dir.glob("*.pdf")))
        logger.info(f"[Semantic Scholar] 현재 PDF 수: {current_count}개")

        if target_count is not None:
            needed = max(0, target_count - current_count)
            if needed == 0:
                logger.info(f"[Semantic Scholar] 목표 {target_count}개 달성 → 다운로드 스킵")
                return 0
            per_sort_results = max(20, needed * 3)
        else:
            per_sort_results = max_results

        sort_mapping = {
            "citation": "citationCount:desc",
            "relevance": "relevance",
            "latest": "publicationDate:desc"
        }

        all_results = {}
        for criterion, weight in weights.items():
            if weight <= 0:
                continue
            sort_value = sort_mapping.get(criterion)
            if not sort_value:
                continue

            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                "query": query,
                "limit": per_sort_results,
                "fields": "title,paperId,authors,year,openAccessPdf,citationCount,url,arxivId",
                "sort": sort_value
            }

            try:
                resp = session.get(url, params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    all_results[criterion] = data.get("data", [])
                    logger.info(f"[Semantic Scholar] {criterion} 기준 검색 완료: {len(all_results[criterion])}개")
                else:
                    logger.warning(f"[Semantic Scholar] {criterion} 검색 실패: {resp.status_code}")
                    all_results[criterion] = []
            except Exception as e:
                logger.error(f"[Semantic Scholar] {criterion} 검색 예외: {e}")
                all_results[criterion] = []

        if not any(all_results.values()):
            logger.info("[Semantic Scholar] 모든 기준에서 결과 없음")
            return 0

        # 점수 계산 및 통합
        paper_scores = {}

        for criterion, papers in all_results.items():
            weight = weights[criterion]
            for rank, paper in enumerate(papers, 1):
                paper_id = paper["paperId"]
                rank_score = 100 * (1 - (rank - 1) / max(len(papers), 1))
                weighted_score = rank_score * weight

                if paper_id not in paper_scores:
                    paper_scores[paper_id] = {"paper": paper, "score": 0.0}
                paper_scores[paper_id]["score"] += weighted_score

        sorted_papers = sorted(paper_scores.items(), key=lambda x: x[1]["score"], reverse=True)

        download_limit = target_count or max_results
        downloaded = 0
        current_llm = Config.SELECTED_MODEL

        for rank, (paper_id, info) in enumerate(sorted_papers[:download_limit], 1):
            paper = info["paper"]
            title = paper.get("title", "제목 없음")
            pdf_url = paper.get("openAccessPdf", {}).get("url")
            arxiv_id = paper.get("arxivId")

            if not pdf_url:
                continue

            if any(
                e.get("title") == title or
                e.get("paper_id") == paper_id or
                e.get("arxiv_id") == arxiv_id
                for e in self.download_history
            ):
                continue

            if arxiv_id:
                logger.info(f"[Semantic Scholar] arXiv ID {arxiv_id} 있음 → arXiv 폴더에 저장됨 → 스킵")
                continue

            filename = self.semantic_paper_dir / f"{paper_id}.pdf"

            try:
                logger.info(f"[Semantic Scholar] 다운로드 시도 ({info['score']:.1f}점, 순위 {rank}위): {title}")
                resp = session.get(pdf_url, timeout=120)
                resp.raise_for_status()
                filename.write_bytes(resp.content)
                logger.info(f"[Semantic Scholar] 다운로드 완료: {title}")

                entry = {
                    "paper_id": paper_id,
                    "title": title,
                    "authors": [a["name"] for a in paper.get("authors", [])],
                    "downloaded_at": datetime.now().isoformat(),
                    "source": "SemanticScholar",
                    "folder": "semantic",
                    "pdf_url": pdf_url,
                    "citation_count": paper.get("citationCount", 0),
                    "download_reason": "mixed_sort",
                    "download_rank": rank,
                    "download_score": round(info["score"], 2),
                    "download_criteria": f"mixed: {weights}"
                }
                self._save_download_history(entry)
                self.download_history.append(entry)
                downloaded += 1

            except Exception as e:
                logger.error(f"[Semantic Scholar] 다운로드 실패: {e}")

        logger.info(f"[Semantic Scholar] 총 {downloaded}개 논문 다운로드 완료 (혼합 정렬)")
        return downloaded


# Prefect 호환 및 테스트 코드
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
    logger.info("=== Paper Manager 최종 테스트 시작 ===")
    logger.info(f"현재 LLM: {Config.SELECTED_MODEL}")
    manager = PaperManager()

    manager.verify_and_cleanup_history(mode="auto")
    manager.scan_user_added_papers()
    manager.download_from_arxiv(max_results=5)
    manager.generate_current_papers_snapshot()

    logger.info("\n현재 오픈소스 목록:")
    for item in manager.get_open_source_list():
        logger.info(f"- {item.get('title')}")
        for link in item.get("github_links", []):
            logger.info(f"  → {link}")

    logger.info("\n테스트 완료!")