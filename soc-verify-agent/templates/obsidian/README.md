# Obsidian Vault — soc-verify-agent

`README.md` (repo) → vault `05-Agents/` 로 복사해 Graph view에서 연결을 본다.

---

## MOC (Map of Content)

| 노트 | 용도 |
|------|------|
| [[00-HUB]] | **시작점** — 역할별 진입, 전체 MOC |
| [[01-GRAPH-FLOW]] | LangGraph 노드·엣지·API |
| [[02-LAYERS]] | Platform / User / MD / ops 레이어 |
| [[03-COMPILED-AI-LOOP]] | MD→Python→재현 루프 |
| [[07-TRUST-CONTRACT]] | tool→codegen→**parity**→canonical (의도 SSOT) |
| [[08-RUNNER-LOOP]] | **LLM 필수** runner 루프 flowchart + 코드 강제 지점 |
| [[04-ARTIFACT-GRAPH]] | 파일·산출물 연결 |
| [[05-GAPS-REMEDIATION]] | 부족한 점 + 보완 (Obsidian+코드) |
| [[06-INDUSTRY-PATTERNS]] | 산업 사례 비교 |
| [[ORCHESTRATOR]] | Main agent 페르소나 |
| [[SUB_AGENT]] | Sub-agent 페르소나 |
| [[MISSION_VERIF-CPU-SOC]] | VERIF 전체 미션 프롬프트 |
| [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]] | VCPU → 고객 SoC **통합 에이전트** |
| [[projects/VERIF-CPU-SOC]] | 프로젝트 gate 그래프 |

---

## Graph view 설정 (권장)

- **필터:** `path:templates/obsidian`
- **색:** `#platform` 노랑, `#project/` 초록, `#gaps` 빨강, `#industry` 파랑
- **고아 노트 방지:** 새 gate 추가 시 `projects/{id}.md`에 링크

---

## 새 프로젝트 추가 시

1. `projects/{PROJECT_ID}.md` 생성 (gate 표 + mermaid)
2. `MISSION_{PROJECT_ID}.md` (선택)
3. [[00-HUB]] MOC에 링크
4. [[04-ARTIFACT-GRAPH]] gate 서브그래프 복제

---

## 코드와 동기화 체크리스트

`registry/graph_flow_spec.yaml` 변경 시 → [[01-GRAPH-FLOW]] 갱신  
`templates/scripts/README.md` 변경 시 → [[04-ARTIFACT-GRAPH#reproduction]] 갱신  
갭 해소 시 → [[05-GAPS-REMEDIATION]] 항목에 ✅