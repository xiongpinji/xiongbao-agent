# V1 Deliverable Checklist

**Status: READY** (verified locally, including Ollama live team)

## Acceptance

```powershell
powershell -File scripts\ensure_ollama.ps1
python -S scripts\verify_v1.py
# → V1 VERIFY OK — deliverable ready
```

| Check | Result |
|---|---|
| Converter unit tests | 8/8 |
| Team runtime tests | 11/11 |
| Bench unit tests | 4/4 |
| Smoke-50 bench | 50/50 (100%) |
| StockPartnerTeam mock demo | OK |
| Local LLM unit (stub) | OK |
| Live Ollama Team (`qwen2.5:1.5b`, 2 members) | OK |

## Artifacts

- `artifacts/bench/` — smoke sample / metrics / report
- `artifacts/live_team/report.json` — local LLM team run

## Local LLM

```powershell
powershell -File scripts\ensure_ollama.ps1
python -S -m octop.contrib.workbuddy.team.live_cli --expert StockPartnerTeam --max-members 2
```

Env: `WB_LLM_BASE_URL` (default `http://127.0.0.1:11434/v1`), `WB_LLM_MODEL`, `WB_LLM_API_KEY`.

## Out of scope (V2 / enterprise)

- Teach recorder + Routine engine
- Casdoor / Milvus / systemd packaging
- Live LLM scoring on Harbor office/code/web/sec subsets
- Full 6-member live team on tiny local models (use `--max-members 0` when using a stronger model)
