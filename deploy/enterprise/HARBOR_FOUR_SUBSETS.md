# Harbor four-subset smoke — V16

Recorded 2026-09-18 (local). `all_ok=true`, total ~455s.

| Job | ok | rc | elapsed_sec |
|---|---|---|---|
| local-openai-cbc-office-smoke | true | 0 | 24.6 |
| local-openai-cbc-code-smoke | true | 0 | 27.2 |
| local-openai-cbc-web-smoke | true | 0 | 381.1 |
| local-openai-cbc-sec-smoke | true | 0 | 22.4 |

## Fixes applied for Windows

- `WB_STAGE_ROOT=C:\wbstage` + `\\?\` copy in `resolve_manifest._stage_dataset` (code subset MAX_PATH)
- Web jobs: `llm_judge_override.enabled=false` + placeholder model (no kimi config locally)
- Runner: `scripts/run_harbor_four_subsets.py` (+ `--full`)

## Full run

```powershell
$env:WB_BENCH_ROOT='W:\'
$env:WB_STAGE_ROOT='C:\wbstage'
$env:AUTO_BUILD_HARNESS_MOUNT='1'
python -S scripts\run_harbor_four_subsets.py --full --timeout 28800
```

Results land in gitignored `artifacts/harbor/four_subsets_full.json` when complete.
