# Deliverable Checklist

## V1 — READY

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
| Model match catalog (profile→pull) | OK |
| Live Ollama Team (`qwen2.5:1.5b`, 2 members) | OK |
| Match+pull `team` → `qwen2.5:3b` | OK |
| Live Ollama Team (`qwen2.5:3b`, 2 members) | OK |

Artifacts: `artifacts/bench/`, `artifacts/live_team/report.json`, `artifacts/live_team/match_team.json`.

## V2 — READY (Teach → Routine MVP)

```powershell
python -S tests\contrib\workbuddy\test_teach_routine.py
# → ALL TEACH/ROUTINE TESTS OK

python -S -m octop.contrib.workbuddy.teach_cli demo
# → TEACH/ROUTINE DEMO OK
```

| Check | Result |
|---|---|
| Record → draft → approve → dry run | OK |
| Test mode requires confirm | OK |
| Bot routine limit (max 50 default; test uses 2) | OK |
| Demo Notion PR → Feishu (recorded path) | OK |

Artifacts: `artifacts/teach_routine/demo_report.json`.

### V2 CLI

```powershell
python -S -m octop.contrib.workbuddy.teach_cli demo
python -S -m octop.contrib.workbuddy.teach_cli list
python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode dry
python -S -m octop.contrib.workbuddy.teach_cli approve --name <skill>
python -S -m octop.contrib.workbuddy.teach_cli create-routine --skill <skill> --bot-id bot-1
```

Safety gates: human approve before create; dry/test/live modes; high-risk steps need approval; stale_data_policy 不复用昨日数据；每 bot 最多 50 routines，保留最近 20 次 run。

### Scheduler（stdlib cron tick）

无需常驻 APScheduler：由系统计划任务每分钟调用 `tick` 即可。

```powershell
python -S tests\contrib\workbuddy\test_routine_scheduler.py
# → ALL SCHEDULER TESTS OK

python -S -m octop.contrib.workbuddy.teach_cli --root artifacts\teach_routine due
python -S -m octop.contrib.workbuddy.teach_cli --root artifacts\teach_routine tick --mode dry
```

| Check | Result |
|---|---|
| 5-field cron match (`*`, `*/n`, ranges) | OK |
| same-minute 不重复触发 | OK |
| `due` preview + `next` | OK |
| Windows 无 tzdata 时 Asia/Shanghai 固定偏移回退 | OK |

## Local LLM（V1）

```powershell
powershell -File scripts\ensure_ollama.ps1
python -S -m octop.contrib.workbuddy.team.match_cli --profile team --vram-gb 4 --pull
$env:WB_LLM_MODEL = "qwen2.5:3b"
python -S -m octop.contrib.workbuddy.team.live_cli --expert StockPartnerTeam --max-members 2
```

Env: `WB_LLM_BASE_URL` (default `http://127.0.0.1:11434/v1`), `WB_LLM_MODEL`, `WB_LLM_API_KEY`.

## Out of scope (later)

- CDP / 浏览器真录制；LLM 自动 drafter；常驻 APScheduler 进程（可用系统 cron + `tick` 替代）
- Casdoor / Milvus / systemd packaging
- Live LLM scoring on Harbor office/code/web/sec subsets
- Full 6-member live team on tiny local models (use `--max-members 0` with a stronger model)
