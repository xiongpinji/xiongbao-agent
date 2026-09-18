# xiongbao-agent — Octop × WorkBuddy

可商用的自托管多 Agent 工作台：**TencentCloud/Octop** + WorkBuddy 专家库 / Team / Teach·Routine。

| 项 | 说明 |
|---|---|
| 上游运行时 | [TencentCloud/Octop](https://github.com/TencentCloud/Octop) v1.0.0（MIT） |
| 专家来源 | `vendor/workbuddy-experts` + `vendor/workbuddyskills` |
| 评测框架 | `vendor/workbuddy-bench`（官方 Harbor 框架；题库需另下） |
| 本仓库远程 | https://github.com/xiongpinji/xiongbao-agent.git |

## 交付范围

**V1（已完成）**

1. **wb2octop 转换器** — 246 专家 → Octop `experts/library/`（245 OK / 1 skip）
2. **Team 运行时** — Supervisor（lead + members），33 个 team 可 materialize
3. **投研 Demo** — `StockPartnerTeam` / `TradingAgentTeam` mock 跑通
4. **Smoke Bench 50 题** — 33 team + 17 agent，结构化 JSONL 指标
5. **本地 LLM** — Ollama OpenAI 兼容调用 + profile→模型匹配下载
6. **验收脚本** — `scripts/verify_v1.py`

**V2（已完成 MVP）**

1. **Teach recorder** — 录制 navigate/read/decision/message 步骤
2. **SkillDraft** — 从录音生成草稿，人工 `approve` 后才能建 Routine
3. **Routine 引擎** — dry / test / live；安全闸门与 bot 上限；run 持久化
4. **CLI + 单测** — `teach_cli` + `test_teach_routine.py`
5. **Scheduler** — stdlib 5 字段 cron + `due`/`tick`（系统计划任务驱动）
6. **LLM drafter** — 规则草稿 + 本地模型润色（`--llm`），人工 approve 仍强制
7. **CDP 录制 + UI 回放** — `cdp-record` / `--cdp-replay`（Chrome 9222）
8. **Connectors** — Notion 读页、飞书 webhook + 开放平台 `im/v1/messages`（`--outbound` + 环境变量门禁）

**V3（已完成 MVP）**

1. **Goal / Craft** — 自然语言目标 → 规划 → 执行 → 逐条验收 → 失败重试
2. **CLI** — `goal_cli demo|plan|run|list`（`--llm` 可选润色）
3. **SkillHub 运行时绑定** — 扫描 `vendor/workbuddyskills/skills`，enable/compose/prompt pack；Team `live_cli --skill` 注入

**V4（商用硬化）**

1. **SkillHub 白名单脚本沙箱** — `skills_cli scripts|exec`，仅 `scripts/` 内相对路径
2. **Goal ← SkillHub** — `goal_cli --skill` 注入 compose 上下文
3. **Outbox 投递日志与重试** — `outbox/delivery.jsonl` + `teach_cli retry-outbox`
4. **验收** — `scripts/verify_v4.py`

**V5（Office + 企业包装文档）**

1. **Office 题库** — `scripts/fetch_office_dataset.ps1`（HF → gitignored datasets）
2. **llm_lite 评分** — 无 Docker；本地 LLM + 启发式/可选 judge（`--office --live-llm`）
3. **systemd + Casdoor/Milvus 文档门禁** — `deploy/systemd/`、`deploy/enterprise/README.md`
4. **验收** — `scripts/verify_v5.py`

延后：Casdoor/Milvus 代码接线；Harbor 全量 Docker verifier。

## 目录要点

```
octop/
  contrib/workbuddy/          # wb2octop + team + bench + teach + routine
  src/octop/.../library/      # 转换后的专家包
vendor/
  workbuddy-experts/
  workbuddyskills/
  workbuddy-bench/            # 官方评测框架（浅克隆）
  RongXinAI/
tests/contrib/workbuddy/
scripts/verify_v1.py
scripts/verify_v4.py
artifacts/bench/              # 评测输出（gitignore）
artifacts/teach_routine/      # Teach/Routine demo 输出
```

## 快速验证（Windows / 无 pytest）

```powershell
cd "D:\AI编程库\项目库\进行中的项目\xiongbao agent"
python -S scripts\verify_v1.py
```

等价分步：

```powershell
python -S tests\contrib\workbuddy\run_tests.py
python -S tests\contrib\workbuddy\test_team_runtime.py
python -S tests\contrib\workbuddy\test_bench.py
python -S -m octop.contrib.workbuddy.bench.cli --sample 50 --out-dir artifacts\bench
python -S tests\contrib\workbuddy\demo_stock_partner.py
```

通过标准：单元测试全绿；smoke-50 **pass rate ≥ 90%**；若本机 Ollama 可用则 live team 真调通过。

## 本地 LLM 真调（Ollama）

前置：Ollama 已安装且 `http://127.0.0.1:11434` 可访问。

### 按需求匹配并下载

| profile | 场景 | 推荐模型 | 约体积 |
|---------|------|----------|--------|
| `smoke` | CI / 2 人冒烟 | `qwen2.5:1.5b` | ~1 GB |
| `team` | 中文 Team（2–4 人，默认） | `qwen2.5:3b` | ~2 GB |
| `team-full` | 6 人专家团 | `qwen2.5:7b` | ~4.7 GB |
| `strong` | 更高质量综合 | `qwen2.5:14b` | ~9 GB |

```powershell
$env:OLLAMA_MODELS = "$env:USERPROFILE\.ollama\models"
# 只匹配
python -S -m octop.contrib.workbuddy.team.match_cli --profile team --vram-gb 4
# 匹配并拉取
python -S -m octop.contrib.workbuddy.team.match_cli --profile team --vram-gb 4 --pull
# 查看目录
python -S -m octop.contrib.workbuddy.team.match_cli --list
```

已安装模型若档位低于需求（例如只要有 `1.5b` 但 profile=`team`），会推荐并拉取更高档，不会误用过弱模型。

若 `OLLAMA_MODELS` 指向损坏的 junction（例如错误的 `C:\ollama_models`），服务会起不来。可临时：

```powershell
$env:OLLAMA_MODELS = "$env:USERPROFILE\.ollama\models"
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

跑 Team 真调（默认最多 2 名成员；`team` 档用 3b）：

```powershell
$env:WB_LLM_MODEL = "qwen2.5:3b"
python -S -m octop.contrib.workbuddy.team.live_cli --expert StockPartnerTeam --max-members 2
```

环境变量：`WB_LLM_BASE_URL`（默认 `http://127.0.0.1:11434/v1`）、`WB_LLM_MODEL`、`WB_LLM_API_KEY`。

## V2 Teach → Routine

```powershell
# 单元测试
python -S tests\contrib\workbuddy\test_teach_routine.py

# 端到端 demo（可选 --llm 润色）
python -S -m octop.contrib.workbuddy.teach_cli demo
python -S -m octop.contrib.workbuddy.teach_cli demo --llm

# 列表 / 审批 / 创建 / 执行 / 润色
python -S -m octop.contrib.workbuddy.teach_cli list
python -S -m octop.contrib.workbuddy.teach_cli polish --name notion-pr-to-feishu --llm
python -S -m octop.contrib.workbuddy.teach_cli approve --name notion-pr-to-feishu
python -S -m octop.contrib.workbuddy.teach_cli create-routine --skill notion-pr-to-feishu --bot-id bot-1
python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode dry
```

模式：`dry`（不落地副作用）→ `test`（需确认）→ `live`。高风险步骤需审批；默认每 bot ≤50 条 Routine。

CDP / Connectors：

```powershell
python -S tests\contrib\workbuddy\test_cdp_live.py
python -S tests\contrib\workbuddy\test_connectors_replay.py

# Chrome 需 --remote-debugging-port=9222
python -S -m octop.contrib.workbuddy.teach_cli cdp-record --url https://example.com --seconds 20
python -S -m octop.contrib.workbuddy.teach_cli connectors
python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode live `
  --live-runner --cdp-replay --outbound
```

Env：`WB_NOTION_TOKEN`、`WB_FEISHU_WEBHOOK` 或 `WB_FEISHU_APP_ID`/`SECRET`/`RECEIVE_ID`、`WB_ALLOW_OUTBOUND=1`。
开放平台目标：`feishu:chat/<chat_id>`、`feishu:open_id/<id>`、`feishu:open`。

调度（每分钟由系统任务调用即可，无需常驻进程）：

```powershell
python -S tests\contrib\workbuddy\test_routine_scheduler.py
python -S -m octop.contrib.workbuddy.teach_cli --root artifacts\teach_routine due
python -S -m octop.contrib.workbuddy.teach_cli --root artifacts\teach_routine tick --mode dry
```

详见 `DELIVERABLE.md`。

## V3 Goal / Craft

```powershell
python -S tests\contrib\workbuddy\test_goal_craft.py
python -S -m octop.contrib.workbuddy.goal_cli demo
python -S -m octop.contrib.workbuddy.goal_cli plan --goal "写入 weekly.md 并通知飞书" --llm
python -S -m octop.contrib.workbuddy.goal_cli run --goal "写入 report.md 并通知飞书" --approve-all
```

流程：规则规划 steps+验收标准 → 可选 `--llm` 润色文案 → LiveStepRunner 执行 → 逐条验收 → 失败可重试。

## SkillHub 运行时绑定

扫描 `vendor/workbuddyskills/skills/*/SKILL.md`，enable / compose / 生成 prompt pack；可注入 Team live 与 Goal。

```powershell
python -S tests\contrib\workbuddy\test_skillhub.py
python -S -m octop.contrib.workbuddy.skills_cli list
python -S -m octop.contrib.workbuddy.skills_cli search diagnose
python -S -m octop.contrib.workbuddy.skills_cli enable diagnose
python -S -m octop.contrib.workbuddy.skills_cli compose --id diagnose
python -S -m octop.contrib.workbuddy.skills_cli scripts --id diagnose
# Goal 绑定 skill：
python -S -m octop.contrib.workbuddy.goal_cli plan --goal "写入 weekly.md" --skill diagnose
# Team 真调时绑定 skill：
python -S -m octop.contrib.workbuddy.team.live_cli --expert StockPartnerTeam --skill diagnose --max-members 2
```

## V4 验收

```powershell
python -S scripts\verify_v4.py
# Outbox 失败重试（需真实凭证时加 --outbound）：
python -S -m octop.contrib.workbuddy.teach_cli retry-outbox --work-dir artifacts\goal_craft\work\<id> --list-only
```

## Windows 计划任务（Routine tick）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\register_routine_tick.ps1
```

详见 `scripts/windows/README.md`。

## 转换专家（如需重跑）

```powershell
python -S -m octop.contrib.workbuddy.cli --vendor vendor --output octop\src\octop\infra\agents\experts\library
```

## 官方 workbuddy-bench（可选）

拉取 Office 50 题（约 3–10MB，gitignore）：

```powershell
powershell -File scripts\fetch_office_dataset.ps1
# 或 Git Bash / WSL:
# cd vendor/workbuddy-bench && ./scripts/dataset/fetch-dataset.sh office
```

本仓库 **smoke-50** 不依赖 HF。Office 有两条路径：

1. **llm_lite（本仓库）** — 本地 LLM 作答 + 启发式/judge，无需 Docker  
2. **全量 Harbor（上游）** — 需 Docker + 官方 verifier

```powershell
python -S -m octop.contrib.workbuddy.bench.cli --office --list-office --dry-sample-only
python -S -m octop.contrib.workbuddy.bench.cli --office --live-llm --limit 3 --no-judge --pass-rate 0.3
python -S scripts\verify_v5.py
```

## 环境要求

- Python **3.11+**（Octop 上游标 3.12+；本桥接层用 `python -S` 可在 3.11 跑通）
- 完整跑 Octop 服务：按 `octop/AGENTS.md`（uv、Node 等）
- 可选：Docker（官方 bench）

## License

- Octop / 本桥接代码：MIT
- WorkBuddy 专家资产：见 `vendor/` 各仓库 NOTICE（MIT / 原作者声明）
- workbuddy-bench：腾讯评测许可，见该仓库 LICENSE
