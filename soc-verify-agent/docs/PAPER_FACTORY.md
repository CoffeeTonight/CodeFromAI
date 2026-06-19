# Paper factory — portable guide

Grok, Claude, ChatGPT, 터미널, CI 어디서든 동일한 워크플로로 논문용 데이터를 준비합니다.

## 설치

```bash
cd soc-verify-agent
pip install -e .
```

등록되는 명령:

- `paper-factory` — 독립 CLI (권장)
- `soc-verify paper …` — 기존 CLI 하위 명령

## 명령 요약

| 목적 | `paper-factory` | `soc-verify` |
|------|-----------------|--------------|
| 준비도 %% | `assess --campaign C --write` | `paper readiness --campaign C --write` |
| verify 제안 | `suggest --campaign C` | `paper suggest --campaign C` |
| 전체 리포트 | `run --campaign C --write` | `paper run --campaign C --write` |
| gate 진행 | `status --campaign C` | `paper status --campaign C` |
| export | `export --campaign C` | `export-paper --campaign C` |

## Python API

```python
from pathlib import Path
from soc_verify.paper_factory import run_factory, suggest_verify_commands, find_repo_root
from soc_verify.paper_readiness import assess_paper_readiness

root = find_repo_root()
report = assess_paper_readiness(root, "paper_eval_2026")
cmds = suggest_verify_commands(root, "paper_eval_2026")
full = run_factory(root, "paper_eval_2026", write=True)
print(full.overall_percent, full.paper_ready)
```

## JSON 연동 (대시보드·다른 AI)

```bash
paper-factory assess --campaign paper_eval_2026 --json > readiness.json
paper-factory suggest --campaign paper_eval_2026 --json > suggestions.json
paper-factory run --campaign paper_eval_2026 --json --write > factory_report.json
```

## 셸만 있는 환경

```bash
export SOC_VERIFY_ROOT=/path/to/soc-verify-agent
./scripts/paper-factory/run.sh paper_eval_2026
```

`pip install` 없이 `PYTHONPATH=src`로 `python -m soc_verify.paper_factory_cli`를 호출합니다.

## 다른 LLM용 프롬프트

아래 블록을 Claude/ChatGPT/Copilot 등에 붙여넣고 캠페인 ID만 바꿔 실행하세요.

---

당신은 soc-verify-agent 논문 제조기 어시스턴트입니다. Grok이 없어도 터미널 명령으로 진행합니다.

**저장소 루트:** `<REPO_ROOT>`
**캠페인:** `<CAMPAIGN>` (예: paper_eval_2026)

### 1단계 — 준비도 확인

```bash
cd <REPO_ROOT>
paper-factory run --campaign <CAMPAIGN> --write
```

또는 JSON:

```bash
paper-factory assess --campaign <CAMPAIGN> --json
```

다음을 사용자에게 보고하세요:

- `overall_percent` — 논문 초안까지 남은 진행률 (100% 목표)
- `verdict` — bootstrap / early_stage / collect_more_data / ready_for_draft
- `dimensions[].gaps` — 부족한 데이터
- `section_status` — 섹션별 작성 가능 여부

### 2단계 — 데이터 수집

```bash
paper-factory suggest --campaign <CAMPAIGN>
```

출력된 `soc-verify verify …` 명령을 사용자에게 제시하고, 실행 후 다시 `paper-factory assess`로 진행률을 확인합니다.

일반 논문 기준: `control` + `treatment_full` 각 ≥5 runs, 총 ≥10, evaluation gates ≥80%.

### 3단계 — export

```bash
paper-factory export --campaign <CAMPAIGN>
```

산출물: `exports/<CAMPAIGN>/runs.csv`, `methods.md`, `paper_readiness.md`

### 4단계 — 초안

`methods.md`와 `runs.csv`를 읽고 Methods/Evaluation/Ablation/Reproducibility 초안을 작성합니다.
아키텍처: `templates/obsidian/11-LANGGRAPH-SUMMARY.md`

명세: `registry/paper_readiness_spec.yaml`, `registry/evaluation_manifest.yaml`

---

## 준비도 기준

`paper_ready=true` 조건:

- overall ≥ 85%
- evaluation gates score ≥ 0.8
- experiment design score ≥ 0.7

자세한 체크리스트: `scripts/paper-factory/README.md`, `.grok/skills/paper-factory/references/paper_checklist.md`