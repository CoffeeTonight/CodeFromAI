---
type: skill
skill_id: paper-progress-judge
tags: [paper, progress, llm-judge]
ast_layer: 06-paper
---

# Paper Progress Judge — LLM 논문 완성도 판단

태그: `#paper` `#progress` `#llm-judge`
입력: `intake/paper_progress_prompt.json` (mechanical readiness + intake AST)
출력: `intake/paper_progress_judgment.json` → `06-paper/PROGRESS.md` sync

---

## 역할

기계적 `paper_readiness` %%만으로는 부족한 **질적 gap**을 판단한다.

- 퍼즐 단계별 **몇 %인지**, **무엇이 부족한지** (한국어)
- 논문 섹션별 **쓸 수 있는지 / 무엇이 더 필요한지**
- 사용자에게 **다음 명령** 3개 이내

## 판단 규칙

1. `mechanical_readiness`를 기본선으로 두되, intake·Obsidian·증거 품질을 보고 `llm_adjustment` (±15 이내) 가능
2. `puzzle_pieces[].percent` — 8단계 모두 채움 (intake → … → draft)
3. `missing[]` — 구체적 (숫자, 경로, 명령). "더 수집 필요" 같은 모호한 문장 금지
4. `overall_percent` — 가중 평균 또는 LLM 판단; **draft** 단계와 정합
5. `paper_ready` — mechanical이 false면 LLM도 true로 올리지 않음 (gate 유지)
6. 인용 없는 낙관 금지 — evidence 없으면 gap으로만 기록

## 출력 JSON (`paper_progress_judgment.json`)

```json
{
  "contract": "paper_progress_judgment_v1",
  "source": "llm",
  "overall_percent": 52.0,
  "mechanical_percent": 48.0,
  "llm_adjustment": 4.0,
  "verdict": "early_stage",
  "paper_ready": false,
  "llm_summary_ko": "한 줄: 전체 52%, 실험·evaluation이 병목…",
  "puzzle_pieces": [
    {"id": "intake", "label_ko": "수집·정리", "percent": 70, "missing": ["…"]}
  ],
  "section_gaps": [
    {"section": "methods", "percent": 35, "writable": false, "missing_ko": "…"}
  ],
  "top_gaps": ["…"],
  "next_commands": ["soc-verify verify …"]
}
```

## sync

판단 저장 후:

```bash
soc-verify paper progress --project ID --campaign paper_eval_2026 --write
```

`06-paper/PROGRESS.md` mermaid 다이어그램의 %%가 갱신된다.