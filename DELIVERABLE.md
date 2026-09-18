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

### LLM drafter（规则 + 本地模型润色）

```powershell
python -S tests\contrib\workbuddy\test_llm_drafter.py
# → ALL LLM DRAFTER TESTS OK

$env:WB_LLM_MODEL = "qwen2.5:3b"
python -S -m octop.contrib.workbuddy.teach_cli demo --llm --out artifacts\teach_routine\demo_llm_report.json
python -S -m octop.contrib.workbuddy.teach_cli polish --name notion-pr-to-feishu --llm
```

| Check | Result |
|---|---|
| Stub polish 保持审批标记 / 步骤数 | OK |
| LLM 失败回退 rules | OK |
| Live `demo --llm` → `source=rules+llm` | OK |

润色只改 trigger / instruction 文案；kind、approvals、安全策略仍以规则草稿为准；润色后 status 回到 `draft`，须重新 approve。

### CDP 真录制 + Live 步骤执行器

Chrome 需开启远程调试：`--remote-debugging-port=9222`。录制通过注入页面脚本轮询 click/type/navigate，写入 TeachRecording（stdlib WebSocket，无需第三方包）。

```powershell
python -S tests\contrib\workbuddy\test_cdp_live.py
# → ALL CDP/LIVE TESTS OK

# 真机录制（需本机 Chrome 已开 9222）
python -S -m octop.contrib.workbuddy.teach_cli cdp-record --url https://example.com --seconds 20

# Live 执行（沙箱写文件 + outbox JSONL；HTTP GET 可选）
python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode test --confirm-test --live-runner --approve step:0
```

| Check | Result |
|---|---|
| CDP client Fake transport RPC | OK |
| CdpTeachSession 事件映射 click/type/navigate | OK |
| LiveStepRunner 沙箱写文件 / outbox / 路径逃逸拒绝 | OK |
| RoutineEngine + LiveStepRunner test 模式 | OK |

`message` 步骤默认写入 `<live-work>/outbox/messages.jsonl`，不静默外发；`click`/`type` 回放标记为 deferred（需 CDP 会话）。

## Local LLM（V1）

```powershell
powershell -File scripts\ensure_ollama.ps1
python -S -m octop.contrib.workbuddy.team.match_cli --profile team --vram-gb 4 --pull
$env:WB_LLM_MODEL = "qwen2.5:3b"
python -S -m octop.contrib.workbuddy.team.live_cli --expert StockPartnerTeam --max-members 2
```

Env: `WB_LLM_BASE_URL` (default `http://127.0.0.1:11434/v1`), `WB_LLM_MODEL`, `WB_LLM_API_KEY`.

## Out of scope (later)

- CDP UI 回放（click/type 真执行）；常驻 APScheduler 进程（可用系统 cron + `tick` 替代）
- Casdoor / Milvus / systemd packaging
- Live LLM scoring on Harbor office/code/web/sec subsets
- Full 6-member live team on tiny local models (use `--max-members 0` with a stronger model)
