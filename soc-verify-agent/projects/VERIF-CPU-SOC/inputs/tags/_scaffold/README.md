# User inputs — tag `{TAG}`

`cache.yaml` → `tag.value: {TAG}` 와 동기화된 입력 폴더입니다.

## 폴더 역할

| 하위 폴더 | 넣을 것 |
|-----------|---------|
| `weekly_release/` | 릴리스 노트, IP delivery checklist |
| `sfr/` | `sfrmap.csv`, 주소맵 리뷰 |
| `deployment/` | intake YAML, hierarchy 복사본, **gen이 안 만드는 MD** |
| `overrides/` | gate JSON override |

파일 추가·변경 시 **`manifest.yaml`** 갱신.

## SoC 통합

- 사람: [`../../howto_integrate2yourSoC.md`](../../howto_integrate2yourSoC.md)
- LLM: [`../../../../templates/obsidian/agent/vcpu-soc-integration/00-INTEGRATION-HUB.md`](../../../../templates/obsidian/agent/vcpu-soc-integration/00-INTEGRATION-HUB.md)
- 새 tag 스캐폴드: [`../copy_new_tag.sh`](../copy_new_tag.sh) · [`12-EXAMPLE-SCAFFOLD`](../../../../templates/obsidian/agent/vcpu-soc-integration/12-EXAMPLE-SCAFFOLD.md)