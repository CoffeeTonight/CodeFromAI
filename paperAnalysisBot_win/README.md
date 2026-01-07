반도체 SoC 설계·검증 분야 LLM/AI 논문 RAG 도구
프로젝트 개요
이 프로젝트는 반도체 SoC 설계 및 검증(Electronic Design Automation, Verification, UVM 등) 분야에서 Large Language Models (LLM)과 AI를 활용한 최신 연구 논문을 자동으로 수집·분석·시각화하는 로컬 RAG(Retrieval-Augmented Generation) 도구입니다.
사용자는 arXiv에서 자동으로 논문을 다운로드하거나 직접 PDF를 추가할 수 있으며, 이를 기반으로 정확하고 신뢰할 수 있는 분석을 제공받습니다. 분석 시 최신 프롬프트 엔지니어링 기법(CoT, Reflection, ReAct 등)을 적용하여 LLM의 환각 현상을 최소화하고, 공개된 오픈소스 구현(GitHub 등)도 함께 정리하여 실제 실험·적용이 가능하도록 설계되었습니다.

1. 프로젝트 목표

arXiv 논문 자동 수집 + 사용자 직접 추가
RAG 기반 고신뢰도 분석 (프롬프트 엔지니어링 + DSPy 적용)
공개 오픈소스(GitHub 등) 자동 추출 및 정리
실무에서 바로 참고·실험 가능한 인사이트 제공
미래 확장: ComfyUI로 tech tree / UVM 다이어그램 등 고품질 이미지 자동 생성

2. 폴더 구조
textpaper_rag_tool/
├── app.py                          # Streamlit UI 진입점
├── config.py                       # 전역 설정 (폴더 경로, 기본 쿼리, LLM config 등)
├── rag_engine.py                   # LlamaIndex + Chroma + PDF→MD + 임베딩
├── paper_manager.py                # arXiv 다운로드, 중복 관리, 오픈소스 자동 추출
├── prompt_manager.py               # prompt_dict + DSPy 기반 프롬프트 최적화
├── scheduler.py                    # Prefect Flow/Deployment 관리 (스케줄링)
├── analysis_report.py              # 전체/특화 분석 (tech tree, trend, 난제 등)
├── open_source_tracker.py          # 오픈소스 검색·정리·저장
├── visualization_manager.py        # ComfyUI API 연결 + 이미지 생성 함수 (미래 확장용)
├── utils.py                        # jsonl 저장/로드, history 관리, 공통 함수
├── workflows/                      # Prefect Flow 정의 폴더 (예: daily_update_flow.py)
└── .db_pallm/
    ├── paper/                      # PDF 저장
    ├── data/                       # MD + Chroma DB
    ├── history/                    # 질문·분석 히스토리 (날짜_시간_제목.jsonl)
    ├── open_source.jsonl           # 오픈소스 정보 백업
    └── download_history.json

4. UI 구성 (Streamlit – 왼쪽 사이드바 탭 이동)
탭 이름주요 내용ChatbotRAG 기반 챗봇, 히스토리 테이블 (checkbox, 앞 15글자 표시, 전체 복사 가능), RAG 요약 editable 사이드바SchedulerPrefect 기반 스케줄 관리 (cron 설정 테이블, 미리 질문 등록, 실행 이력)LLM SettingJSON 입력으로 회사 GLM 등 LLM 설정Overall Tech Report전체 트렌드, tech tree (mermaid), 난제·리스크·미래 방향 분석LLM Design AutomationRTL/HLS 생성, 설계 최적화 특화 분석LLM Verification AutomationTestbench/Assertion/Bug fixing 특화 분석Open Source Projects논문별 공개 GitHub/Zenodo/Hugging Face 정리 (링크 클릭 가능, 실행 가이드)

5. 핵심 기술 및 도구

UI: Streamlit (최종 사용자 인터페이스)
파이프라인·테스트·스케줄링: Prefect (Flow/Task로 모듈 단위 테스트, Orion UI로 시각화, Deployment로 스케줄링)
시각화 확장: ComfyUI (API 연결로 tech tree, UVM 다이어그램 등 고품질 이미지 생성 – 미래 준비)
RAG 백엔드: LlamaIndex + Chroma
PDF 처리: PyMuPDF4LLM (MD 변환)
프롬프트 엔지니어링: DSPy (CoT, Self-Reflection, ReAct, ToT 자동 적용)
오픈소스 추출: PDF 파싱 + 논문 제목 기반 웹 검색

6. 개발 원칙

모듈화 + 파일 분리: 각 파일은 하나의 책임만
독립 테스트 가능: 모든 파일에 Prefect Task/Flow 또는 간단한 __main__ 테스트 함수 포함 → python 파일명.py로 바로 동작 확인
Prefect 중심 개발: 로직 완성 → 테스트 → Streamlit UI에 연결
확장성: ComfyUI 연결 함수 미리 설계 (visualization_manager.py)
신뢰도: 모든 분석 프롬프트는 DSPy + CoT/Reflection/ReAct 적용

7. 개발 순서 (Prefect 우선 → Streamlit 마무리)

Prefect 설치 및 Orion UI 확인
각 모듈을 Prefect Task/Flow로 구현 (독립 테스트)
전체 Flow 연결 및 스케줄링 테스트
Streamlit UI에 Prefect 결과 연결
ComfyUI 연결 함수 설계 (옵션 버튼으로)