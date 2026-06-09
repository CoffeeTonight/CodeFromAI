# Archived RTL (Windows MAX_PATH)

`rtl/soc_top/...` 아래 깊은 `u_*` 경로는 Windows 기본 경로 길이 제한(260자)을 초과합니다.
해당 `.v` 파일은 짧은 이름으로 이 폴더에 보관되어 있으며, 원래 경로는 `MANIFEST.tsv`에 기록되어 있습니다.

## 기본 체크아웃 (Windows / 짧은 경로)

- `quick.hc.f` — Windows-safe shallow subset (~23 sources)
- `top_deep_soc.hc.f` — 전체 filelist는 유지되나, deep RTL 없으면 ingest 실패

## 부분 복원 (Windows-safe 짧은 경로)

긴 `u_*` 디렉터리명을 줄여 `MAX_PATH` 이내 파일을 `rtl/`로 복원합니다.

```bash
python3 scripts/restore_synthetic_partial.py
```

- `PATH_ALIAS.tsv` — `original_path` → `restored_path` 매핑
- `quick.hc.f` — 복원된 RTL 목록으로 자동 갱신
- 아직 `missings/`에 남는 파일은 짧은 경로로도 260자를 초과하는 deep leaf

## 전체 원본 경로 복원 (Linux / macOS, 경로 제한 없음)

```bash
python3 scripts/restore_synthetic_deep_rtl.py
```

## 다시 아카이브

```bash
python3 scripts/archive_windows_long_paths.py --design synthetic_deep_rtl
```