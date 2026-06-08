# verif_cpu_project (legacy / optional)

**공식 VerifCPU 검증 패키지는 `../verif_cpu_verilog/` 입니다.**

Campaign 펌웨어, icode 빌드, iverilog 시뮬, VCD 게이트는 모두 **verilog 트리 안**에 있습니다.

```
../verif_cpu_verilog/
├── rtl/ tb/ include/
├── firmware/campaign/    ← 이전에 여기 있던 빌드가 이동됨
├── tools/probe_icodes.py
├── Makefile
└── example.sh
```

이 디렉터리에 남은 것:

| 경로 | 용도 |
|------|------|
| `python_model/` | (선택) behavior model cross-check |
| `docs/` | 설계 메모 |
| `firmware/` | campaign 외 펌웨어 예제 |

**Verilog만 사용할 때** `verif_cpu_verilog`만 복사·배포하면 됩니다. `verif_cpu_project`는 필요 없습니다.