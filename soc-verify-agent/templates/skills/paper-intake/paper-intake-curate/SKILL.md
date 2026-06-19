---
type: skill
skill_id: paper-intake-curate
tags: [paper, intake, llm-primary]
ast_layer: 04-skills
---

# Paper-Grade Intake Curation — LLM 주 작업 지침

태그: `#paper` `#intake` `#curation`
입력: `intake/knowledge_bundle.json` · `05-intake/sources/*.md`
출력: 논문급 Obsidian 노트 + 정규화된 project note

---

## 1. 수집물 분류 (Evidence typing)

각 소스를 아래 **하나**로 태깅하고 frontmatter `evidence_type`에 기록:

| evidence_type | 예시 소스 | 논문 용도 |
|---------------|-----------|-----------|
| `project_meta` | discovered.yaml, Confluence 과제页 | Introduction·Setup |
| `verification_spec` | gate CHECK, verification manifest | Methods·Evaluation setup |
| `experiment_log` | run summary, verdict JSON | Results |
| `llm_trace` | llm_telemetry, prompt JSON | Methods (provenance) |
| `improvement` | ablation, scorecard, code_change_log | Ablation·Discussion |
| `repro` | repro_bundle listing, env_pin | Reproducibility |
| `related_work` | wiki, external doc | Related work |

## 2. 논문급 Obsidian 노트 구조 (소스별)

`05-intake/sources/{id}.md` 를 **다음 섹션으로 보강** (없으면 추가):

```markdown
## Paper claim (1 sentence)
검증 가능한 단일 주장. 예: "GPIO ext gate PASS under treatment_full with II≥0.75."

## Provenance chain
- primary: `intake/knowledge_bundle.json#sources[N]`
- derived: (run_id, gate path, export row) — 없으면 `TBD`

## Extracted facts (bullet, each cited)
- [S1] fact … (`source_id`, line or JSON path)
- [S2] …

## Numbers table (if any)
| metric | value | unit | source_ref | condition |
|--------|-------|------|------------|-----------|

## Gaps for paper
- missing: (e.g. control runs <5, no llm_telemetry)
- next_collect: (bash command or artifact path)

## Section mapping
- methods: …
- evaluation: …
- ablation: …
```

**규칙:** 모든 수치·PASS/FAIL은 `source_ref` 필수. 추측 금지 → `TBD` + gap.

## 3. SOURCES-MOC 보강

`05-intake/SOURCES-MOC.md` 하단에 추가:

- **By evidence_type** — 타입별 소스 wikilink 목록
- **Paper gaps (top 5)** — `paper readiness` 차원별 부족 항목
- **Campaign tag** — `paper_eval_2026` 등

## 4. Project note 정규화 (`normalize`)

`templates/obsidian/projects/{id}.md` 작성 시:

1. Overview — 과제 목적 (Confluence/wiki에서만; 없으면 "TBD")
2. **## Paper experiment design** — campaign, conditions, hypotheses (스킬 [[paper-experiment-design]] 참조)
3. **## Verification gates (evaluation set)** — stage/group 표 + evaluation_manifest role
4. **## Evidence index** — `05-intake` wikilink + evidence_type 요약
5. **## Sources** — intake 소스 목록 (type, path, collected_at)
6. **## Paper readiness snapshot** — 가능하면 차원별 gap 1줄 (아니면 "run paper readiness")

## 5. intake.json AST sidecar

`05-intake/intake.json` 에 추가 필드:

```json
{
  "paper_curation": {
    "curated_at": "ISO8601",
    "evidence_by_type": { "project_meta": ["slug-1"] },
    "gaps": ["control runs: 2/5"],
    "campaign": "paper_eval_2026",
    "section_coverage": { "methods": 0.4, "evaluation": 0.2 }
  }
}
```

## 6. 품질 체크리스트 (완료 전)

- [ ] 모든 표 행에 source_ref
- [ ] control / treatment 분리 서술
- [ ] gate id = repo 경로와 일치 (stage/group)
- [ ] LLM 생성 문단에 model·run_id 또는 `TBD`
- [ ] [[04-skills/paper-section-mapping]] 과 모순 없음

## 7. 명령 (수집 후)

```bash
soc-verify paper readiness --campaign paper_eval_2026 --write
soc-verify paper suggest --campaign paper_eval_2026
```