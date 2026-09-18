# Harbor live score — V15 smoke

Recorded 2026-09-18 (local).

| Field | Value |
|---|---|
| ok | true |
| mode | live |
| job | `local-openai-cbc-office-smoke` |
| returncode | 0 |
| elapsed_sec | ~120.8 |
| task | `analyst-forecast-extract-L3-018` |
| harness_mount | `workbuddy-bench/harness/codebuddy-code:2.103.4` |
| model | `qwen2.5:3b` (via `WB_LLM_*`) |

Notes:

- First failure: missing harness mount → fixed with `AUTO_BUILD_HARNESS_MOUNT=1`
- Second failure: `harbor.exe` not on PATH for Windows `Popen` → `harbor_score_entry` prepends bench `.venv/Scripts`
- Full stdout tails stay under gitignored `artifacts/harbor/`
