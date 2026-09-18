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

`message` 步骤默认写入 `<live-work>/outbox/messages.jsonl`，不静默外发；无 CDP 会话时 `click`/`type` 回放标记为 deferred。

### Connectors + CDP UI 回放 + 真外发

```powershell
python -S tests\contrib\workbuddy\test_connectors_replay.py
# → ALL CONNECTOR/REPLAY TESTS OK

# 探测 Notion / 飞书配置（不写密钥到仓库）
python -S -m octop.contrib.workbuddy.teach_cli connectors

# CDP 回放 click/type（需 Chrome 9222）+ 可选飞书外发
$env:WB_NOTION_TOKEN = "<token>"
$env:WB_FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/..."
# 或开放平台 im/v1/messages：
# $env:WB_FEISHU_APP_ID="cli_xxx"; $env:WB_FEISHU_APP_SECRET="xxx"
# $env:WB_FEISHU_RECEIVE_ID="oc_xxx"; $env:WB_ALLOW_OUTBOUND="1"
python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode live `
  --live-runner --cdp-replay --outbound --approve step:0
```

| Check | Result |
|---|---|
| Notion page id 解析 + Fake HTTP 读页 | OK |
| Feishu webhook 无 `WB_ALLOW_OUTBOUND` 拦截 / Fake POST | OK |
| Feishu open API tenant_token + im/v1/messages | OK |
| CdpReplaySession FakeTransport click/type/navigate | OK |
| LiveStepRunner + CDP + Feishu 联通 | OK |

Env: `WB_NOTION_TOKEN`、`WB_FEISHU_WEBHOOK` 或 `WB_FEISHU_APP_ID`/`SECRET`/`RECEIVE_ID`、`WB_ALLOW_OUTBOUND=1`（`--outbound` 时 CLI 会置位）。
目标前缀：`notion:page/<id>`、`feishu:webhook`、`feishu:chat/<id>`、`feishu:open`。

## Local LLM（V1）

```powershell
powershell -File scripts\ensure_ollama.ps1
python -S -m octop.contrib.workbuddy.team.match_cli --profile team --vram-gb 4 --pull
$env:WB_LLM_MODEL = "qwen2.5:3b"
python -S -m octop.contrib.workbuddy.team.live_cli --expert StockPartnerTeam --max-members 2
```

Env: `WB_LLM_BASE_URL` (default `http://127.0.0.1:11434/v1`), `WB_LLM_MODEL`, `WB_LLM_API_KEY`.

### Goal / Craft + 逐条验收（V3 MVP）

自然语言目标 → 规则规划 steps + criteria → LiveStepRunner 执行 → 验收器逐条检查 → 失败可重试。

```powershell
python -S tests\contrib\workbuddy\test_goal_craft.py
# → ALL GOAL/CRAFT TESTS OK

python -S -m octop.contrib.workbuddy.goal_cli demo
python -S -m octop.contrib.workbuddy.goal_cli plan --goal "写入 weekly.md 并通知飞书"
python -S -m octop.contrib.workbuddy.goal_cli plan --goal "写入 weekly.md 并通知飞书" --llm
python -S -m octop.contrib.workbuddy.goal_cli run --goal "写入 report.md 并通知飞书" --approve-all
```

| Check | Result |
|---|---|
| 规则规划 write + message + criteria | OK |
| file_exists / file_contains / outbox_message / step_ok | OK |
| GoalEngine 端到端 accepted | OK |
| 缺审批时 error 拦截 | OK |
| `--llm` 润色保持 kind/审批/（目标）（内容）标记 | OK |

验收种类：`file_exists`、`file_contains`、`outbox_message`、`step_ok`。高风险步骤需 `--approve-all` 或 `--approve step:N`。
LLM 润色仅改 instruction/description；结构与安全闸门仍由规则规划决定。

### SkillHub 运行时绑定（MVP）

扫描 vendor skills → enable/compose → 生成 `COMPOSED_SYSTEM.md` prompt pack；Team `live_cli --skill` 注入。

```powershell
python -S tests\contrib\workbuddy\test_skillhub.py
# → ALL SKILLHUB TESTS OK

python -S -m octop.contrib.workbuddy.skills_cli index
python -S -m octop.contrib.workbuddy.skills_cli compose --ids diagnose,handoff
```

| Check | Result |
|---|---|
| frontmatter 无 PyYAML 解析 | OK |
| catalog scan / search / get | OK |
| enable + compose_system | OK |
| materialize prompt pack | OK |
| live_cli `--skill` 注入路径 | OK |

## V4 — READY（沙箱 / Goal--skill / Outbox 重试）

```powershell
python -S scripts\verify_v4.py
# → V4 VERIFY OK
```

| Check | Result |
|---|---|
| SkillHub `scripts/` 白名单沙箱（禁 path escape / shell=True） | OK |
| `skills_cli scripts` / `exec` | OK |
| Goal `plan/run --skill` 注入 Bound Skills | OK |
| `outbox/delivery.jsonl` + `retry-outbox` | OK |
| `scripts/verify_v4.py` | OK |

```powershell
python -S -m octop.contrib.workbuddy.skills_cli scripts --id <skill>
python -S -m octop.contrib.workbuddy.goal_cli plan --goal "写入 x.md" --skill handoff
python -S -m octop.contrib.workbuddy.teach_cli retry-outbox --work-dir <live-work> --list-only
python -S -m octop.contrib.workbuddy.teach_cli retry-outbox --work-dir <live-work> --outbound
```

### Windows 计划任务（V5.1）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\register_routine_tick.ps1
# 默认每分钟 dry tick；上线：-Mode live
powershell -File scripts\windows\unregister_routine_tick.ps1
```

详见 `scripts/windows/README.md`。

## V5.2 / V5.3 — READY（Office llm-lite + 企业包装文档）

```powershell
powershell -File scripts\fetch_office_dataset.ps1
python -S scripts\verify_v5.py
# → V5 VERIFY OK

# 可选：本地 Ollama 对 2 道 office 题做 llm_lite 评分
python -S scripts\verify_v5.py --live --limit 2 --pass-rate 0
```

| Check | Result |
|---|---|
| `fetch_office_dataset.ps1` 拉取/解压 office 50 题 | OK（数据集 gitignore） |
| `llm_judge` 启发式 + 假 LLM 单测 | OK |
| `--office --live-llm` 本地评分路径（无 Docker） | OK |
| `deploy/systemd/*.service|timer` | OK |
| `deploy/enterprise/README.md` Casdoor/Milvus 门禁 | OK（文档约定，未接线） |

```powershell
python -S -m octop.contrib.workbuddy.bench.cli --office --list-office --dry-sample-only
python -S -m octop.contrib.workbuddy.bench.cli --office --live-llm --limit 3 --no-judge --pass-rate 0.3
```

说明：`llm_lite` ≠ 官方 Harbor verifier；全量 Docker Harbor 仍属后续。

## V6 — READY（Ask/Plan/Craft · 记忆 · 路由 · 连接器扩展 · verify_all）

```powershell
python -S scripts\verify_all.py
# → VERIFY ALL OK — WorkBuddy V6 board green

# 可选：拉取 code/web/sec 题库（office 已有可用 fetch_office_dataset.ps1）
powershell -File scripts\fetch_bench_subsets.ps1 -Subset office,code,web
python -S -m octop.contrib.workbuddy.bench.cli --list-subsets --dry-sample-only
```

| Check | Result |
|---|---|
| `modes_cli assemble` Ask/Plan/Craft | OK |
| `memory` 加载 SOUL/USER/MEMORY + 挂 Team/Goal | OK |
| 钉钉/企微 webhook + `connectors_cli`（103 包目录） | OK |
| `router_cli route` 专家自动匹配 | OK |
| SkillHub 含 builtin（skill-creator 等） | OK |
| `enterprise_cli probe` Casdoor/Milvus 软探测 | OK |
| `verify_all.py` | OK |

```powershell
python -S -m octop.contrib.workbuddy.modes_cli assemble --mode craft --workspace .
python -S -m octop.contrib.workbuddy.router_cli route --query "股票分析" --limit 5
python -S -m octop.contrib.workbuddy.connectors_cli list --limit 10
python -S -m octop.contrib.workbuddy.goal_cli run --goal "写 x.md" --work-mode ask   # 应拒绝执行
```

## Out of scope (later)

- 常驻 APScheduler 进程（可用系统 cron / systemd timer + `tick` 替代）
- Casdoor / Milvus **JWT/RAG 运行时接线**（软探测 + 文档门禁已就绪）
- 全量 Harbor Docker 评分（code/web/sec + 官方 office verifier）
- Full 6-member live team on tiny local models (use `--max-members 0` with a stronger model)
