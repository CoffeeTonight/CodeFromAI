# Paper factory (portable)

Grok 없이 터미널·다른 AI·CI에서 논문용 데이터 준비도를 확인하고 export합니다.

## 설치

```bash
cd /path/to/soc-verify-agent
pip install -e .
```

`paper-factory`와 `soc-verify` 명령이 PATH에 등록됩니다.

## 빠른 시작

```bash
# 준비도 (몇 % 남았는지)
paper-factory assess --campaign paper_eval_2026 --write

# 부족한 데이터 → verify 명령 제안
paper-factory suggest --campaign paper_eval_2026

# 한 번에 (assess + suggest + 파일 저장)
paper-factory run --campaign paper_eval_2026 --write

# export (CSV + Methods)
paper-factory export --campaign paper_eval_2026
```

동일 기능을 `soc-verify paper`로도 사용할 수 있습니다:

```bash
soc-verify --root . paper readiness --campaign paper_eval_2026 --write
soc-verify --root . paper suggest --campaign paper_eval_2026
soc-verify --root . paper run --campaign paper_eval_2026 --write
soc-verify --root . export-paper --campaign paper_eval_2026
```

## 셸 스크립트 (pip 없이)

```bash
export SOC_VERIFY_ROOT=/path/to/soc-verify-agent
export PYTHONPATH="$SOC_VERIFY_ROOT/src:$PYTHONPATH"

./scripts/paper-factory/run.sh paper_eval_2026
```

## JSON (다른 도구 연동)

```bash
paper-factory assess --campaign paper_eval_2026 --json
paper-factory suggest --campaign paper_eval_2026 --json
paper-factory run --campaign paper_eval_2026 --json --write
```

## 산출물

`exports/<campaign>/`:

| 파일 | 용도 |
|------|------|
| `paper_readiness.json` / `.md` | 준비도·gap |
| `suggested_commands.sh` | 다음 verify 명령 |
| `runs.csv`, `methods.md` | 논문 표·Methods |

## 다른 AI에게 붙여넣기

`docs/PAPER_FACTORY.md`의 **LLM 프롬프트** 섹션을 Claude/ChatGPT/Copilot 등에 복사하세요.